"""Evaluation CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import time as time_module
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from cutctx.evals.benchmark_report import BenchmarkSuiteResult

from .main import main

BENCHMARK_PRESETS: dict[str, dict[str, list[str]]] = {
    "llmlingua_research": {
        "datasets": [
            "code_samples",
            "rag_samples",
            "mixed_agent_traces",
            "verbatim_compaction",
        ],
        "compressors": ["content_router", "llmlingua"],
        "metrics": [
            "ratio",
            "tokens_saved",
            "tokens_per_second",
            "f1",
            "information_recall",
            "critical_item_recall",
            "verbatim_fidelity",
        ],
    }
}


@main.group()
def evals() -> None:
    """Memory evaluations and compressor benchmark commands.

    \b
    Examples:
        cutctx evals benchmark    Run cross-compressor benchmark (ratio, F1, ROUGE-L)
        cutctx evals memory       Run LoCoMo memory evaluation
        cutctx evals memory-v2    Run V2 evaluation with LLM-controlled tools
    """
    pass


@evals.command("memory")
@click.option(
    "--n-conversations",
    "-n",
    type=int,
    help="Number of conversations to evaluate (default: all 10)",
)
@click.option(
    "--categories",
    help="Comma-separated list of categories 1-5 (default: 1,2,3,4)",
)
@click.option(
    "--include-adversarial",
    is_flag=True,
    help="Include category 5 (unanswerable questions)",
)
@click.option(
    "--top-k",
    type=int,
    default=10,
    help="Number of memories to retrieve per question (default: 10)",
)
@click.option(
    "--f1-threshold",
    type=float,
    default=0.5,
    help="F1 score threshold for 'correct' (default: 0.5)",
)
@click.option(
    "--answer-model",
    help="LLM model for generating answers (e.g., gpt-4o, claude-sonnet-4-20250514)",
)
@click.option(
    "--llm-judge",
    is_flag=True,
    help="Use LLM-as-judge scoring",
)
@click.option(
    "--judge-provider",
    type=click.Choice(["openai", "anthropic", "litellm", "simple"]),
    default="litellm",
    help="LLM judge provider (default: litellm - uses same model as answer-model)",
)
@click.option(
    "--judge-model",
    default="gpt-4o",
    help="Model for LLM judge (default: gpt-4o)",
)
@click.option(
    "--output",
    "-o",
    help="Path to save JSON results",
)
@click.option(
    "--no-extract",
    is_flag=True,
    help="Disable LLM memory extraction (store raw dialogue instead)",
)
@click.option(
    "--extraction-model",
    default="gpt-4o-mini",
    help="Model for memory extraction (default: gpt-4o-mini)",
)
@click.option(
    "--pass-all",
    is_flag=True,
    help="Pass ALL memories to LLM (Path A: no retrieval bottleneck)",
)
@click.option(
    "--parallel",
    type=int,
    default=10,
    help="Number of parallel workers for LLM calls (default: 10)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (saved to results JSON)",
)
def memory_eval(
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    top_k: int,
    f1_threshold: float,
    answer_model: str | None,
    llm_judge: bool,
    judge_provider: str,
    judge_model: str,
    output: str | None,
    no_extract: bool,
    extraction_model: str,
    pass_all: bool,
    parallel: int,
    debug: bool,
) -> None:
    """Run LoCoMo memory evaluation benchmark.

    \b
    LoCoMo (Long-term Conversational Memory) tests memory across:
    - Single-hop questions (simple fact recall)
    - Temporal questions (time-based)
    - Multi-hop questions (reasoning across memories)
    - Open-domain questions (interpretation required)

    \b
    Examples:
        cutctx evals memory -n 3
        cutctx evals memory --answer-model gpt-4o --llm-judge
    """
    _run_memory_eval(
        n_conversations=n_conversations,
        categories=categories,
        include_adversarial=include_adversarial,
        top_k=top_k,
        f1_threshold=f1_threshold,
        answer_model=answer_model,
        llm_judge=llm_judge,
        judge_provider=judge_provider,
        judge_model=judge_model,
        output=output,
        no_extract=no_extract,
        extraction_model=extraction_model,
        pass_all=pass_all,
        parallel=parallel,
        debug=debug,
    )


@evals.command("memory-v2")
@click.option(
    "--n-conversations",
    "-n",
    type=int,
    help="Number of conversations to evaluate (default: all 10)",
)
@click.option(
    "--categories",
    help="Comma-separated list of categories 1-5 (default: 1,2,3,4)",
)
@click.option(
    "--include-adversarial",
    is_flag=True,
    help="Include category 5 (unanswerable questions)",
)
@click.option(
    "--f1-threshold",
    type=float,
    default=0.5,
    help="F1 score threshold for 'correct' (default: 0.5)",
)
@click.option(
    "--save-model",
    default="gpt-4o-mini",
    help="LLM model for deciding what to save (default: gpt-4o-mini)",
)
@click.option(
    "--answer-model",
    default="gpt-4o",
    help="LLM model for answering questions (default: gpt-4o)",
)
@click.option(
    "--max-results",
    type=int,
    default=10,
    help="Maximum memories to retrieve per search (default: 10)",
)
@click.option(
    "--no-graph",
    is_flag=True,
    help="Disable graph expansion in search",
)
@click.option(
    "--llm-judge",
    is_flag=True,
    help="Use LLM-as-judge scoring",
)
@click.option(
    "--judge-model",
    default="gpt-4o",
    help="Model for LLM judge (default: gpt-4o)",
)
@click.option(
    "--output",
    "-o",
    help="Path to save JSON results",
)
@click.option(
    "--parallel",
    type=int,
    default=5,
    help="Number of parallel workers for LLM calls (default: 5)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (saved to results JSON)",
)
def memory_eval_v2(
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    f1_threshold: float,
    save_model: str,
    answer_model: str,
    max_results: int,
    no_graph: bool,
    llm_judge: bool,
    judge_model: str,
    output: str | None,
    parallel: int,
    debug: bool,
) -> None:
    """Run LoCoMo V2 evaluation with LLM-controlled memory tools.

    \b
    This evaluator tests the new architecture where:
    - LLM decides what to save (memory_save tool)
    - LLM decides when to search (memory_search tool)
    - Graph relationships enable multi-hop reasoning

    \b
    Examples:
        cutctx evals memory-v2 -n 3
        cutctx evals memory-v2 --answer-model gpt-4o --save-model gpt-4o-mini
    """
    _run_memory_eval_v2(
        n_conversations=n_conversations,
        categories=categories,
        include_adversarial=include_adversarial,
        f1_threshold=f1_threshold,
        save_model=save_model,
        answer_model=answer_model,
        max_results=max_results,
        no_graph=no_graph,
        llm_judge=llm_judge,
        judge_model=judge_model,
        output=output,
        parallel=parallel,
        debug=debug,
    )


# -----------------------------------------------------------------------------
# Backwards compatibility: old command names (hidden)
# -----------------------------------------------------------------------------


@main.command("memory-eval", hidden=True)
@click.option("--n-conversations", "-n", type=int)
@click.option("--categories")
@click.option("--include-adversarial", is_flag=True)
@click.option("--top-k", type=int, default=10)
@click.option("--f1-threshold", type=float, default=0.5)
@click.option("--answer-model")
@click.option("--llm-judge", is_flag=True)
@click.option(
    "--judge-provider",
    type=click.Choice(["openai", "anthropic", "litellm", "simple"]),
    default="litellm",
)
@click.option("--judge-model", default="gpt-4o")
@click.option("--output", "-o")
@click.option("--no-extract", is_flag=True)
@click.option("--extraction-model", default="gpt-4o-mini")
@click.option("--pass-all", is_flag=True)
@click.option("--parallel", type=int, default=10)
@click.option("--debug", is_flag=True)
def memory_eval_compat(
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    top_k: int,
    f1_threshold: float,
    answer_model: str | None,
    llm_judge: bool,
    judge_provider: str,
    judge_model: str,
    output: str | None,
    no_extract: bool,
    extraction_model: str,
    pass_all: bool,
    parallel: int,
    debug: bool,
) -> None:
    """Deprecated: Use 'cutctx evals memory' instead."""
    click.echo("Note: 'memory-eval' is deprecated. Use 'cutctx evals memory'", err=True)
    _run_memory_eval(
        n_conversations=n_conversations,
        categories=categories,
        include_adversarial=include_adversarial,
        top_k=top_k,
        f1_threshold=f1_threshold,
        answer_model=answer_model,
        llm_judge=llm_judge,
        judge_provider=judge_provider,
        judge_model=judge_model,
        output=output,
        no_extract=no_extract,
        extraction_model=extraction_model,
        pass_all=pass_all,
        parallel=parallel,
        debug=debug,
    )


@main.command("memory-eval-v2", hidden=True)
@click.option("--n-conversations", "-n", type=int)
@click.option("--categories")
@click.option("--include-adversarial", is_flag=True)
@click.option("--f1-threshold", type=float, default=0.5)
@click.option("--save-model", default="gpt-4o-mini")
@click.option("--answer-model", default="gpt-4o")
@click.option("--max-results", type=int, default=10)
@click.option("--no-graph", is_flag=True)
@click.option("--llm-judge", is_flag=True)
@click.option("--judge-model", default="gpt-4o")
@click.option("--output", "-o")
@click.option("--parallel", type=int, default=5)
@click.option("--debug", is_flag=True)
def memory_eval_v2_compat(
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    f1_threshold: float,
    save_model: str,
    answer_model: str,
    max_results: int,
    no_graph: bool,
    llm_judge: bool,
    judge_model: str,
    output: str | None,
    parallel: int,
    debug: bool,
) -> None:
    """Deprecated: Use 'cutctx evals memory-v2' instead."""
    click.echo("Note: 'memory-eval-v2' is deprecated. Use 'cutctx evals memory-v2'", err=True)
    _run_memory_eval_v2(
        n_conversations=n_conversations,
        categories=categories,
        include_adversarial=include_adversarial,
        f1_threshold=f1_threshold,
        save_model=save_model,
        answer_model=answer_model,
        max_results=max_results,
        no_graph=no_graph,
        llm_judge=llm_judge,
        judge_model=judge_model,
        output=output,
        parallel=parallel,
        debug=debug,
    )


# -----------------------------------------------------------------------------
# Implementation functions (shared by new and compat commands)
# -----------------------------------------------------------------------------


def _run_memory_eval(
    *,
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    top_k: int,
    f1_threshold: float,
    answer_model: str | None,
    llm_judge: bool,
    judge_provider: str,
    judge_model: str,
    output: str | None,
    no_extract: bool,
    extraction_model: str,
    pass_all: bool,
    parallel: int,
    debug: bool,
) -> None:
    """Run LoCoMo memory evaluation."""
    # Suppress noisy pydantic warnings from litellm
    import warnings

    warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*")
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    try:
        from cutctx.evals.memory import (
            LoCoMoEvaluator,
            MemoryEvalConfig,
            create_anthropic_judge,
            create_litellm_judge,
            create_openai_judge,
            simple_judge,
        )
        from cutctx.memory import MemoryConfig
    except ImportError as e:
        click.echo("Error: Memory eval dependencies not installed.")
        click.echo("Run: pip install cutctx[memory,evals]")
        click.echo(f"Details: {e}")
        raise SystemExit(1) from None

    import asyncio

    # Build configuration
    parsed_categories = None
    if categories:
        parsed_categories = [int(c) for c in categories.split(",")]

    memory_config = MemoryConfig()

    eval_config = MemoryEvalConfig(
        n_conversations=n_conversations,
        categories=parsed_categories,
        skip_adversarial=not include_adversarial,
        top_k_memories=top_k,
        llm_judge_enabled=llm_judge,
        llm_judge_model=judge_model,
        memory_config=memory_config,
        f1_threshold=f1_threshold,
        extract_memories=not no_extract,
        extraction_model=extraction_model,
        pass_all_memories=pass_all,
        parallel_workers=parallel,
        debug=debug,
    )

    # Create answer function based on provider
    answer_fn = None
    if answer_model:
        try:
            import litellm

            def answer_fn(question: str, memories: list[str]) -> str:
                if not memories:
                    return "I don't have information about that."

                # Format memories - use all if pass_all, else top 10
                context = "\n".join(f"- {m}" for m in memories)

                prompt = f"""You are answering questions about a conversation between two people based on extracted memories/facts.

## Memories from the conversation:
{context}

## Question: {question}

## Instructions:
1. Find the specific fact(s) in the memories that answer this question
2. Answer with JUST the key information requested - be concise
3. For "when" questions: give the specific date if mentioned (e.g., "7 May 2023", "2022")
4. For "what" questions: give the specific thing/action
5. For "who" questions: give the name
6. If the exact answer is in the memories, use those exact words/dates
7. If you cannot find the answer, say "Information not found"

## Answer (be concise - just the facts):"""

                response = litellm.completion(
                    model=answer_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=150,
                )
                return response.choices[0].message.content or ""

        except ImportError:
            click.echo("Error: litellm required for --answer-model. Run: pip install litellm")
            raise SystemExit(1) from None

    # Create LLM judge if enabled
    llm_judge_fn: Callable[[str, str, str], tuple[float, str]] | None = None
    if llm_judge:
        # Use answer model for judge if not explicitly set
        effective_judge_model = judge_model
        if answer_model and judge_model == "gpt-4o":
            effective_judge_model = answer_model  # Match the answer model

        if judge_provider == "simple":
            llm_judge_fn = simple_judge
        elif judge_provider == "openai":
            llm_judge_fn = create_openai_judge(model=effective_judge_model)
        elif judge_provider == "anthropic":
            llm_judge_fn = create_anthropic_judge(model=effective_judge_model)
        else:
            llm_judge_fn = create_litellm_judge(model=effective_judge_model)

    # Determine judge info for display
    judge_info = "DISABLED"
    if llm_judge:
        if judge_provider == "simple":
            judge_info = "ENABLED (rule-based F1)"
        else:
            jm = judge_model
            if answer_model and judge_model == "gpt-4o":
                jm = answer_model
            judge_info = f"ENABLED ({judge_provider}: {jm})"

    extract_info = f"ENABLED ({extraction_model})" if not no_extract else "DISABLED (raw dialogue)"
    retrieval_info = "ALL memories (Path A)" if pass_all else f"Top-{top_k} retrieval"

    click.echo(f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                    CUTCTX MEMORY EVALUATION                          ║
║                         LoCoMo Benchmark                               ║
╚═══════════════════════════════════════════════════════════════════════╝

Configuration:
  Conversations:    {n_conversations or "all"}
  Categories:       {parsed_categories or "[1,2,3,4]"}
  Retrieval:        {retrieval_info}
  Memory Extract:   {extract_info}
  Answer Model:     {answer_model or "default (retrieval)"}
  LLM Judge:        {judge_info}
  Parallelism:      {parallel} workers
  Debug:            {"ENABLED" if debug else "DISABLED"}

Running evaluation...
""")

    # Run evaluation
    evaluator = LoCoMoEvaluator(
        answer_fn=answer_fn,
        llm_judge_fn=llm_judge_fn,
        config=eval_config,
    )

    try:
        result = asyncio.run(evaluator.run())
    except KeyboardInterrupt:
        click.echo("\nEvaluation interrupted.")
        raise SystemExit(1) from None

    # Print results
    click.echo(result.summary())

    # Save results if output path specified
    if output:
        result.save(output)
        click.echo(f"\nResults saved to: {output}")


def _run_memory_eval_v2(
    *,
    n_conversations: int | None,
    categories: str | None,
    include_adversarial: bool,
    f1_threshold: float,
    save_model: str,
    answer_model: str,
    max_results: int,
    no_graph: bool,
    llm_judge: bool,
    judge_model: str,
    output: str | None,
    parallel: int,
    debug: bool,
) -> None:
    """Run LoCoMo V2 memory evaluation (LLM-controlled tools)."""
    # Suppress noisy pydantic warnings from litellm
    import warnings

    warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*")
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    try:
        from cutctx.evals.memory import (
            LoCoMoEvaluatorV2,
            MemoryEvalConfigV2,
        )
    except ImportError as e:
        click.echo("Error: Memory eval V2 dependencies not installed.")
        click.echo("Run: pip install cutctx[memory,evals]")
        click.echo(f"Details: {e}")
        raise SystemExit(1) from None

    import asyncio

    # Build configuration
    parsed_categories = None
    if categories:
        parsed_categories = [int(c) for c in categories.split(",")]

    eval_config = MemoryEvalConfigV2(
        n_conversations=n_conversations,
        categories=parsed_categories,
        skip_adversarial=not include_adversarial,
        llm_judge_enabled=llm_judge,
        llm_judge_model=judge_model,
        f1_threshold=f1_threshold,
        parallel_workers=parallel,
        debug=debug,
        save_model=save_model,
        answer_model=answer_model,
        max_search_results=max_results,
        include_graph_expansion=not no_graph,
    )

    click.echo(f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                   CUTCTX MEMORY EVALUATION V2                        ║
║              LLM-Controlled Memory Architecture                        ║
╚═══════════════════════════════════════════════════════════════════════╝

Configuration:
  Conversations:    {n_conversations or "all"}
  Categories:       {parsed_categories or "[1,2,3,4]"}
  Save Model:       {save_model}
  Answer Model:     {answer_model}
  Max Results:      {max_results}
  Graph Expansion:  {"DISABLED" if no_graph else "ENABLED"}
  LLM Judge:        {"ENABLED" if llm_judge else "DISABLED"}
  Parallelism:      {parallel} workers
  Debug:            {"ENABLED" if debug else "DISABLED"}

Key Differences from V1:
  - LLM decides WHAT to save (memory_save tool)
  - LLM decides HOW to search (memory_search tool)
  - Graph expansion enables multi-hop reasoning

Running evaluation...
""")

    # Run evaluation
    evaluator = LoCoMoEvaluatorV2(
        answer_model=answer_model,
        config=eval_config,
    )

    try:
        result = asyncio.run(evaluator.run())
    except KeyboardInterrupt:
        click.echo("\nEvaluation interrupted.")
        raise SystemExit(1) from None

    # Print results
    click.echo(result.summary())

    # Save results if output path specified
    if output:
        result.save(output)
        click.echo(f"\nResults saved to: {output}")


@evals.command("probes")
@click.option(
    "--recordings",
    "recordings_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory of JSONL recordings written via CUTCTX_PROBE_RECORD_DIR.",
)
@click.option(
    "--eval-dataset",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to custom evaluation JSONL dataset (overrides default).",
)
@click.option(
    "--json-output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional machine-readable JSON report output.",
)
def run_probes(recordings_dir: Path, eval_dataset: Path | None, json_output: Path | None) -> None:
    """Score retention of recorded compression events (offline, no LLM).

    \b
    Record sessions first by running the proxy with
    CUTCTX_PROBE_RECORD_DIR set. Recordings contain full conversation
    content in plaintext and stay on this machine.
    """
    import json as json_module

    from cutctx.evals.session_probes import render_report, run_probes

    # Check for empty or no-valid-files directory before probing
    recording_files = sorted(recordings_dir.glob("*.jsonl"))
    if not recording_files:
        click.echo(f"No recordings found in {recordings_dir}")
        return

    report = run_probes(recordings_dir)
    click.echo(render_report(report))
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json_module.dumps(report.to_dict(), indent=2), encoding="utf-8")
        click.echo(f"\nWrote JSON report: {json_output}")


# -----------------------------------------------------------------------------
# Benchmark command
# -----------------------------------------------------------------------------


@evals.command("benchmark")
@click.option(
    "--dataset",
    "-d",
    multiple=True,
    default=["tool_outputs"],
    help="Dataset name(s). Available: tool_outputs, longbench, squad, hotpotqa, ...",
)
@click.option(
    "--preset",
    type=click.Choice(sorted(BENCHMARK_PRESETS.keys())),
    default=None,
    help="Named benchmark preset. Overrides dataset, compressor, and metric selection.",
)
@click.option(
    "--longbench-task",
    default="qasper",
    help="LongBench subtask (qasper, multifieldqa_en, narrativeqa)",
)
@click.option(
    "--n",
    "n_samples",
    type=int,
    default=50,
    help="Samples per dataset",
)
@click.option(
    "--compressors",
    "-c",
    multiple=True,
    type=click.Choice(
        [
            "raw_passthrough",
            "smart_crusher",
            "log",
            "search",
            "diff",
            "code",
            "kompress",
            "llmlingua",
            "drain3",
            "verbatim_compactor",
            "content_router",
            "all",
        ]
    ),
    default=["all"],
    help="Compressors to benchmark",
)
@click.option(
    "--metrics",
    multiple=True,
    type=click.Choice(
        [
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
    ),
    default=[
        "ratio",
        "f1",
        "information_recall",
        "critical_item_recall",
        "tokens_per_second",
        "verbatim_fidelity",
    ],
    help="Metrics to compute",
)
@click.option("--parallel", type=int, default=4)
@click.option("--output", "-o", type=str, default=None, help="Save JSON results to PATH")
@click.option(
    "--markdown",
    is_flag=True,
    default=False,
    help="Also save markdown table",
)
@click.option(
    "--html",
    "html_output",
    is_flag=True,
    default=False,
    help="Also save an HTML report",
)
@click.option("--seed", type=int, default=42)
@click.option(
    "--disable-hf-xet",
    is_flag=True,
    default=False,
    help="Use standard Hugging Face HTTP downloads instead of the optional Xet transport.",
)
@click.option(
    "--hf-download-timeout",
    type=click.IntRange(min=1),
    default=None,
    help="Override Hugging Face model-download timeout in seconds for live baselines.",
)
@click.option(
    "--llmlingua-model",
    default=None,
    help="Override the LLMLingua model ID for a reproducible comparison run.",
)
@click.option(
    "--publish",
    is_flag=True,
    default=False,
    help="Append this run's results to docs/benchmarks.md (idempotent per day).",
)
def benchmark(
    dataset: tuple[str, ...],
    preset: str | None,
    longbench_task: str,
    n_samples: int,
    compressors: tuple[str, ...],
    metrics: tuple[str, ...],
    parallel: int,
    output: str | None,
    markdown: bool,
    html_output: bool,
    seed: int,
    disable_hf_xet: bool,
    hf_download_timeout: int | None,
    llmlingua_model: str | None,
    publish: bool,
) -> None:
    """Run a reproducible compressor benchmark on standard datasets.

    \b
    Compresses each dataset's contexts through every selected compressor,
    then produces a comparison table (LLMLingua-paper style) showing
    compression ratios, F1 retention, and information recall.

    \b
    Examples:
        cutctx evals benchmark -d tool_outputs -n 10
        cutctx evals benchmark -d tool_outputs -d squad --output results.json
        cutctx evals benchmark --compressors smart_crusher content_router log
    """
    if disable_hf_xet:
        # Hugging Face reads this before the optional model is first constructed.
        os.environ["HF_HUB_DISABLE_XET"] = "1"
    if hf_download_timeout is not None:
        os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(hf_download_timeout)

    _run_benchmark(
        datasets=list(dataset),
        preset=preset,
        longbench_task=longbench_task,
        n_samples=n_samples,
        compressors=list(compressors),
        metrics=list(metrics),
        parallel=parallel,
        output=output,
        markdown=markdown,
        html_output=html_output,
        seed=seed,
        llmlingua_model=llmlingua_model,
        publish=publish,
    )


main.add_command(benchmark, name="benchmark")


@evals.command("verify")
@click.option(
    "--dataset",
    "-d",
    multiple=True,
    default=["tool_outputs"],
    help="Dataset name(s). Available: tool_outputs, longbench, squad, hotpotqa, ...",
)
@click.option(
    "--longbench-task",
    default="qasper",
    help="LongBench subtask (qasper, multifieldqa_en, narrativeqa)",
)
@click.option(
    "--n",
    "n_samples",
    type=int,
    default=8,
    help="Samples per dataset",
)
@click.option(
    "--compressors",
    "-c",
    multiple=True,
    type=click.Choice(
        [
            "raw_passthrough",
            "smart_crusher",
            "log",
            "search",
            "diff",
            "code",
            "kompress",
            "llmlingua",
            "drain3",
            "verbatim_compactor",
            "content_router",
            "all",
        ]
    ),
    default=["content_router", "smart_crusher"],
    help="Compressors to verify",
)
@click.option("--parallel", type=int, default=4)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.option("--output", "-o", type=str, default=None, help="Write the report to PATH")
@click.option("--ci", is_flag=True, help="Exit non-zero when thresholds are not met.")
@click.option(
    "--min-f1",
    type=float,
    default=0.9,
    show_default=True,
    help="Minimum F1 score required for PASS.",
)
@click.option(
    "--min-information-recall",
    type=float,
    default=0.9,
    show_default=True,
    help="Minimum information recall required for PASS.",
)
@click.option(
    "--max-compression-ratio",
    type=float,
    default=0.95,
    show_default=True,
    help="Maximum average compression ratio allowed for PASS.",
)
@click.option(
    "--max-latency-ms",
    type=float,
    default=250.0,
    show_default=True,
    help="Maximum average latency per compressor in milliseconds.",
)
@click.option(
    "--min-critical-item-recall",
    type=float,
    default=0.9,
    show_default=True,
    help="Minimum critical-item recall required for PASS when available.",
)
@click.option(
    "--min-verbatim-fidelity",
    type=float,
    default=0.9,
    show_default=True,
    help="Minimum verbatim fidelity required for PASS when available.",
)
@click.option(
    "--min-tokens-per-second",
    type=float,
    default=0.0,
    show_default=True,
    help="Minimum throughput required for PASS when non-zero.",
)
def verify(
    dataset: tuple[str, ...],
    longbench_task: str,
    n_samples: int,
    compressors: tuple[str, ...],
    parallel: int,
    fmt: str,
    output: str | None,
    ci: bool,
    min_f1: float,
    min_information_recall: float,
    max_compression_ratio: float,
    max_latency_ms: float,
    min_critical_item_recall: float,
    min_verbatim_fidelity: float,
    min_tokens_per_second: float,
) -> None:
    """Run a CI-friendly compressor verification benchmark.

    
    The verify command is a compact benchmark surface for CI. It records
    git SHA, dataset names, compressor names, token savings, compression
    ratio, F1, information recall, latency, and a pass/fail verdict.

    
    Examples:
        cutctx verify --ci
        cutctx verify --format json -o verify.json
        cutctx verify -d tool_outputs -c content_router -c smart_crusher
    """
    report = _run_verify(
        datasets=list(dataset),
        longbench_task=longbench_task,
        n_samples=n_samples,
        compressors=list(compressors),
        parallel=parallel,
        thresholds={
            "min_f1": min_f1,
            "min_information_recall": min_information_recall,
            "max_compression_ratio": max_compression_ratio,
            "max_latency_ms": max_latency_ms,
            "min_critical_item_recall": min_critical_item_recall,
            "min_verbatim_fidelity": min_verbatim_fidelity,
            "min_tokens_per_second": min_tokens_per_second,
        },
    )

    content = _render_verify_report(report, fmt=fmt)
    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Verify report written to: {output}")
    else:
        click.echo(content)

    if ci and not report["pass"]:
        raise SystemExit(1)


main.add_command(verify, name="verify")


# -----------------------------------------------------------------------------
# Benchmark implementation
# -----------------------------------------------------------------------------


def _resolve_benchmark_preset(preset: str) -> tuple[list[str], list[str], list[str]]:
    """Return dataset, compressor, and metric selections for *preset*."""
    config = BENCHMARK_PRESETS[preset]
    return (
        list(config["datasets"]),
        list(config["compressors"]),
        list(config["metrics"]),
    )


def _run_benchmark(
    *,
    datasets: list[str],
    preset: str | None,
    longbench_task: str,
    n_samples: int,
    compressors: list[str],
    metrics: list[str],
    parallel: int,
    output: str | None,
    markdown: bool,
    html_output: bool,
    seed: int,
    llmlingua_model: str | None,
    publish: bool,
) -> None:
    """Core benchmark logic."""
    import warnings

    # Suppress noisy UserWarning from optional dependencies
    warnings.filterwarnings("ignore", category=UserWarning)

    from cutctx.evals.benchmark_runner import BenchmarkRunner
    from cutctx.evals.datasets import load_dataset_by_name

    selected_datasets = list(datasets)
    selected_compressors = list(compressors)
    selected_metrics = list(metrics)

    if preset is not None:
        selected_datasets, selected_compressors, selected_metrics = _resolve_benchmark_preset(
            preset
        )

    # Print banner
    click.echo(
        f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                    CUTCTX COMPRESSOR BENCHMARK                       ║
║                  Reproducible Cross-Compressor Comparison               ║
╚═══════════════════════════════════════════════════════════════════════╝

Configuration:
  Datasets:         {", ".join(selected_datasets)}
  Samples/dataset:  {n_samples}
  Compressors:      {", ".join(selected_compressors) if "all" not in selected_compressors else "all available"}
  Metrics:          {", ".join(selected_metrics)}
  Preset:           {preset or "custom"}
  Parallelism:      {parallel} workers
  Seed:             {seed}
  LLMLingua model:  {llmlingua_model or "default"}
"""
    )

    runner = BenchmarkRunner(llmlingua_model=llmlingua_model)

    # Resolve compressor selection
    all_comp_keys = (
        sorted(runner._adapters.keys())
        if hasattr(runner, "_adapters")
        else [a.name for a in runner.list_compressors()]
    )
    if "all" in selected_compressors:
        selected_compressors = all_comp_keys

    # Warn about missing optional compressors
    adapters = {a.name: a for a in runner.list_compressors()}
    for comp_key in selected_compressors:
        adapter = adapters.get(comp_key)
        if adapter and not adapter.available:
            click.echo(f"  ⚠  Compressor '{comp_key}' not available (install optional deps)")
    click.echo("")

    # Expand "all" datasets if needed
    if "all" in selected_datasets:
        from cutctx.evals.datasets import list_available_datasets

        by_cat = list_available_datasets()
        selected_datasets = [ds for cat_list in by_cat.values() for ds in cat_list]

    # Accumulate results across datasets
    all_results = []
    all_datasets = []
    total_start = time_module.time()

    for ds_name in selected_datasets:
        click.echo(f"Loading dataset: {ds_name} ... ", nl=False)

        kwargs = {}
        if ds_name == "longbench":
            kwargs["task"] = longbench_task

        # Some datasets (e.g. tool_outputs) are fixed-size and don't accept n
        from cutctx.evals.datasets import DATASET_REGISTRY

        ds_info = DATASET_REGISTRY.get(ds_name, {})
        if ds_info.get("default_n") is not None:
            kwargs.setdefault("n", n_samples)

        try:
            suite = load_dataset_by_name(ds_name, **kwargs)
        except ImportError as exc:
            click.echo(f"SKIPPED (missing dependency: {exc})")
            continue
        except Exception as exc:
            click.echo(f"ERROR: {exc}")
            continue

        click.echo(f"{len(suite.cases)} cases loaded")

        # Cap to n_samples
        n_actual = min(n_samples, len(suite.cases))

        click.echo(f"  Running {len(selected_compressors)} compressors ...")

        suite_result = runner.run(
            dataset=suite,
            compressors=selected_compressors,
            metrics=selected_metrics,
            n=n_actual,
            parallel=parallel,
            seed=seed,
        )

        all_results.extend(suite_result.results)
        all_datasets.append(suite.name)

    total_duration = time_module.time() - total_start

    # Build final result
    from cutctx.evals.benchmark_report import BenchmarkSuiteResult

    benchmark_metadata = {}
    if "llmlingua" in selected_compressors:
        benchmark_metadata["llmlingua_model"] = (
            llmlingua_model or "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
        )

    final = BenchmarkSuiteResult(
        seed=seed,
        compressors=selected_compressors,
        datasets=all_datasets,
        results=all_results,
        metadata=benchmark_metadata,
    )
    final.totals["duration_seconds"] = total_duration
    final._compute_totals()

    # Print summary
    _print_benchmark_summary(final)

    # Save JSON
    if output:
        final.save(output)
        click.echo(f"\nResults saved to: {output}")

    # Save markdown
    if markdown or output:
        md_path = str(Path(output).with_suffix(".md")) if output else "benchmark_results.md"
        if markdown:
            md_content = _build_markdown_report(final, selected_metrics)
            Path(md_path).write_text(md_content, encoding="utf-8")
            click.echo(f"Markdown saved to: {md_path}")

    if html_output or output:
        html_path = str(Path(output).with_suffix(".html")) if output else "benchmark_results.html"
        if html_output:
            html_content = _build_html_report(final, selected_metrics)
            Path(html_path).write_text(html_content, encoding="utf-8")
            click.echo(f"HTML saved to: {html_path}")

    # Publish: append a dated section to docs/benchmarks.md
    if publish:
        publish_content = (
            md_content if markdown else _build_markdown_report(final, selected_metrics)
        )
        _publish_benchmark_results(
            publish_content,
            seed=seed,
            datasets=all_datasets,
            compressors=selected_compressors,
        )


def _print_benchmark_summary(result: BenchmarkSuiteResult) -> None:
    """Print a human-readable summary of benchmark results."""
    active = [r for r in result.results if not r.skipped]
    skipped = [r for r in result.results if r.skipped]

    click.echo(f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                         BENCHMARK SUMMARY                            ║
╚═══════════════════════════════════════════════════════════════════════╝

  Datasets:              {len(result.datasets)}
  Compressors tested:    {len(active)} / {len(result.results)}
  Skipped:               {len(skipped)}
  Errors:                {sum(r.errors for r in active)}
  Duration:              {result.totals.get("duration_seconds", 0):.1f}s

  Compression Ratios:
""")

    for r in active:
        ratio_pct = f"{r.ratio * 100:.1f}%"
        emoji = "✓" if r.ratio < 0.9 else " "
        click.echo(
            f"    {emoji} {r.compressor:20s}  {ratio_pct:>8s}  ({r.tokens_saved:,} tokens saved)"
        )

    # Print metric tables for F1 / IR
    for metric in (
        "tokens_per_second",
        "f1",
        "information_recall",
        "critical_item_recall",
        "verbatim_fidelity",
    ):
        vals = [
            (r.compressor, getattr(r, metric)) for r in active if getattr(r, metric) is not None
        ]
        if vals:
            label = {
                "tokens_per_second": "Tokens / Second",
                "f1": "F1 Score",
                "information_recall": "Information Recall",
                "critical_item_recall": "Critical Item Recall",
                "verbatim_fidelity": "Verbatim Fidelity",
            }.get(metric, metric)
            click.echo(f"\n  {label}:")
            for comp_name, val in vals:
                if metric == "tokens_per_second":
                    click.echo(f"    {comp_name:20s}  {val:,.1f}")
                else:
                    click.echo(f"    {comp_name:20s}  {val:.3f}")


def _build_markdown_report(result: BenchmarkSuiteResult, metrics: list[str]) -> str:
    """Build a full markdown report with one table per metric."""
    lines = [
        "# Cutctx Compressor Benchmark Report",
        "",
        f"Seed: `{result.seed}` | "
        f"Duration: {result.totals.get('duration_seconds', 0):.1f}s | "
        f"Datasets: {', '.join(result.datasets)}",
        "",
    ]
    for metric in metrics:
        lines.append(result.to_markdown(metric))
        if len(result.compressors) > 1:
            lines.append(result.to_relative_markdown(metric, baseline=result.compressors[0]))
        lines.append("")
    lines.append("_Generated by `cutctx evals benchmark`_")
    return "\n".join(lines)


def _build_html_report(result: BenchmarkSuiteResult, metrics: list[str]) -> str:
    """Build a full HTML benchmark report with one table per metric."""
    sections: list[str] = []
    for metric in metrics:
        sections.append(result.to_html(metric))
        if len(result.compressors) > 1:
            sections.append(result.to_relative_html(metric, baseline=result.compressors[0]))
    sections_html = "\n".join(sections)
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Cutctx Compressor Benchmark Report</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #111827; }}
      table {{ border-collapse: collapse; width: 100%; margin: 16px 0 32px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; }}
      th {{ background: #f3f4f6; }}
      h1, h2 {{ margin: 0 0 12px; }}
      p {{ margin: 0 0 24px; color: #4b5563; }}
      code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <h1>Cutctx Compressor Benchmark Report</h1>
    <p>Seed: <code>{result.seed}</code> | Duration: {result.totals.get("duration_seconds", 0):.1f}s | Datasets: {", ".join(result.datasets)}</p>
    {sections_html}
    <p><em>Generated by <code>cutctx evals benchmark</code></em></p>
  </body>
</html>
"""


def _publish_benchmark_results(
    md_content: str,
    *,
    seed: int,
    datasets: list[str],
    compressors: list[str],
) -> None:
    """Append a dated cutctx evals benchmark run to docs/benchmarks.md.

    Idempotent per calendar day: re-running --publish the same day
    replaces that day's section instead of duplicating it.
    """
    from datetime import date

    docs_path = Path(__file__).resolve().parents[2] / "docs" / "benchmarks.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    heading = f"## `cutctx evals benchmark` — {today}"
    section = (
        f"{heading}\n\n"
        f"Datasets: {', '.join(datasets)} · Compressors: {', '.join(compressors)} · Seed: {seed}\n\n"
        f"{md_content}\n"
    )
    existing = (
        docs_path.read_text(encoding="utf-8") if docs_path.exists() else "# Cutctx Benchmarks\n"
    )
    if heading in existing:
        before, _, after = existing.partition(heading)
        next_idx = after.find("\n## `cutctx evals benchmark` — ")
        rest = after[next_idx:] if next_idx != -1 else ""
        existing = before + section + rest
    else:
        existing = existing.rstrip("\n") + "\n\n" + section
    docs_path.write_text(existing, encoding="utf-8")
    click.echo(f"Published results to: {docs_path}")


def _get_git_sha() -> str:
    """Return the current repository SHA, or ``unknown`` if unavailable."""
    repo_root = Path(__file__).resolve().parents[2]

    for args in (("git", "rev-parse", "--short", "HEAD"), ("git", "rev-parse", "HEAD")):
        try:
            proc = subprocess.run(
                args,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return "unknown"
        if proc.returncode == 0:
            sha = proc.stdout.strip()
            if sha:
                return sha
    return "unknown"


def _run_verify(
    *,
    datasets: list[str],
    longbench_task: str,
    n_samples: int,
    compressors: list[str],
    parallel: int,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    """Run the benchmark runner and normalize the results for CI reporting."""
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning)

    from cutctx.evals.benchmark_runner import BenchmarkRunner
    from cutctx.evals.datasets import DATASET_REGISTRY, load_dataset_by_name

    runner = BenchmarkRunner()

    all_comp_keys = (
        sorted(runner._adapters.keys())
        if hasattr(runner, "_adapters")
        else [a.name for a in runner.list_compressors()]
    )
    if "all" in compressors:
        selected_compressors = all_comp_keys
    else:
        selected_compressors = compressors

    if "all" in datasets:
        from cutctx.evals.datasets import list_available_datasets

        by_cat = list_available_datasets()
        datasets = [ds for cat_list in by_cat.values() for ds in cat_list]

    selected_datasets = list(datasets)
    loaded_datasets: list[str] = []
    all_results = []
    skipped_compressors: list[str] = []
    total_start = time_module.time()

    adapters = {a.name: a for a in runner.list_compressors()}
    for comp_key in selected_compressors:
        adapter = adapters.get(comp_key)
        if adapter is None or not adapter.available:
            skipped_compressors.append(comp_key)

    for ds_name in selected_datasets:
        kwargs: dict[str, Any] = {}
        if ds_name == "longbench":
            kwargs["task"] = longbench_task

        ds_info = DATASET_REGISTRY.get(ds_name, {})
        if ds_info.get("default_n") is not None:
            kwargs.setdefault("n", n_samples)

        try:
            suite = load_dataset_by_name(ds_name, **kwargs)
        except ImportError:
            continue
        except Exception:
            continue

        loaded_datasets.append(suite.name)
        suite_result = runner.run(
            dataset=suite,
            compressors=selected_compressors,
            metrics=[
                "ratio",
                "tokens_saved",
                "tokens_per_second",
                "f1",
                "information_recall",
                "critical_item_recall",
                "verbatim_fidelity",
            ],
            n=min(n_samples, len(suite.cases)),
            parallel=parallel,
            seed=42,
            warmup_cases=1,
        )
        all_results.extend(suite_result.results)

    total_duration = time_module.time() - total_start

    final = BenchmarkSuiteResult(
        seed=42,
        compressors=selected_compressors,
        datasets=loaded_datasets,
        results=all_results,
    )
    final.totals["duration_seconds"] = total_duration
    final._compute_totals()

    return _build_verify_report(
        final,
        git_sha=_get_git_sha(),
        selected_datasets=selected_datasets,
        selected_compressors=selected_compressors,
        thresholds=thresholds,
        skipped_compressors=skipped_compressors,
    )


def _build_verify_report(
    result: BenchmarkSuiteResult,
    *,
    git_sha: str,
    selected_datasets: list[str],
    selected_compressors: list[str],
    thresholds: dict[str, float],
    skipped_compressors: list[str],
) -> dict[str, Any]:
    """Build a machine-readable verification report."""
    active = [r for r in result.results if not r.skipped]
    skipped = [r for r in result.results if r.skipped]
    rows: list[dict[str, Any]] = []

    for row in result.results:
        row_thresholds: list[str] = []
        status = "PASS"
        critical_item_recall = None
        critical_item_recall_source = None
        verbatim_fidelity = row.verbatim_fidelity

        if row.skipped:
            status = "SKIP"
            row_thresholds.append("compressor unavailable")
        else:
            if row.tokens_saved <= 0:
                row_thresholds.append("tokens_saved <= 0")
            if row.ratio > thresholds["max_compression_ratio"]:
                row_thresholds.append(
                    f"compression_ratio {row.ratio:.3f} > {thresholds['max_compression_ratio']:.3f}"
                )
            if row.f1 is None or row.f1 < thresholds["min_f1"]:
                row_thresholds.append(
                    f"f1 {0.0 if row.f1 is None else row.f1:.3f} < {thresholds['min_f1']:.3f}"
                )
            if (
                row.information_recall is None
                or row.information_recall < thresholds["min_information_recall"]
            ):
                row_thresholds.append(
                    "information_recall "
                    f"{0.0 if row.information_recall is None else row.information_recall:.3f} "
                    f"< {thresholds['min_information_recall']:.3f}"
                )
            if row.avg_ms > thresholds["max_latency_ms"]:
                row_thresholds.append(
                    f"latency_ms {row.avg_ms:.2f} > {thresholds['max_latency_ms']:.2f}"
                )
            if thresholds["min_tokens_per_second"] > 0 and (
                row.tokens_per_second is None
                or row.tokens_per_second < thresholds["min_tokens_per_second"]
            ):
                row_thresholds.append(
                    "tokens_per_second "
                    f"{0.0 if row.tokens_per_second is None else row.tokens_per_second:.1f} "
                    f"< {thresholds['min_tokens_per_second']:.1f}"
                )
            if row.critical_item_recall is not None:
                critical_item_recall = row.critical_item_recall
                critical_item_recall_source = "benchmark_metric"
                if critical_item_recall < thresholds["min_critical_item_recall"]:
                    row_thresholds.append(
                        "critical_item_recall "
                        f"{critical_item_recall:.3f} < {thresholds['min_critical_item_recall']:.3f}"
                    )
            elif row.dataset == "ToolOutputSamples" and row.information_recall is not None:
                critical_item_recall = row.information_recall
                critical_item_recall_source = "information_recall_proxy"
            if (
                verbatim_fidelity is not None
                and verbatim_fidelity < thresholds["min_verbatim_fidelity"]
            ):
                row_thresholds.append(
                    "verbatim_fidelity "
                    f"{verbatim_fidelity:.3f} < {thresholds['min_verbatim_fidelity']:.3f}"
                )

            if row_thresholds:
                status = "FAIL"

        rows.append(
            {
                "dataset": row.dataset,
                "compressor": row.compressor,
                "tokens_saved": row.tokens_saved,
                "compression_ratio": round(row.ratio, 4),
                "f1": round(row.f1, 4) if row.f1 is not None else None,
                "information_recall": round(row.information_recall, 4)
                if row.information_recall is not None
                else None,
                "critical_item_recall": round(critical_item_recall, 4)
                if critical_item_recall is not None
                else None,
                "critical_item_recall_source": critical_item_recall_source,
                "tokens_per_second": round(row.tokens_per_second, 2)
                if row.tokens_per_second is not None
                else None,
                "verbatim_fidelity": round(verbatim_fidelity, 4)
                if verbatim_fidelity is not None
                else None,
                "latency_ms": round(row.avg_ms, 2),
                "p50_latency_ms": round(row.p50_ms, 2),
                "status": status,
                "pass": status == "PASS",
                "reasons": row_thresholds,
                "skipped": row.skipped,
            }
        )

    overall_pass = bool(active) and not skipped and all(row["pass"] for row in rows)

    return {
        "git_sha": git_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": selected_datasets[0] if len(selected_datasets) == 1 else selected_datasets,
        "datasets": selected_datasets,
        "compressors": selected_compressors,
        "thresholds": {
            "min_f1": thresholds["min_f1"],
            "min_information_recall": thresholds["min_information_recall"],
            "max_compression_ratio": thresholds["max_compression_ratio"],
            "max_latency_ms": thresholds["max_latency_ms"],
            "min_critical_item_recall": thresholds["min_critical_item_recall"],
            "min_verbatim_fidelity": thresholds["min_verbatim_fidelity"],
            "min_tokens_per_second": thresholds["min_tokens_per_second"],
        },
        "summary": {
            "datasets": len(result.datasets),
            "compressors": len(selected_compressors),
            "rows": len(rows),
            "passed": sum(1 for row in rows if row["status"] == "PASS"),
            "failed": sum(1 for row in rows if row["status"] == "FAIL"),
            "skipped": sum(1 for row in rows if row["status"] == "SKIP"),
            "duration_ms": round(result.totals.get("duration_seconds", 0.0) * 1000, 2),
            "tokens_saved": sum(row["tokens_saved"] for row in rows if not row["skipped"]),
        },
        "results": rows,
        "skipped_compressors": skipped_compressors,
        "pass": overall_pass,
    }


def _render_verify_report(report: dict[str, Any], *, fmt: str) -> str:
    """Render a verification report in text, JSON, or Markdown."""
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True)
    if fmt == "markdown":
        return _render_verify_markdown(report)
    return _render_verify_text(report)


def _render_verify_text(report: dict[str, Any]) -> str:
    """Render a compact terminal summary."""
    status = "PASS" if report["pass"] else "FAIL"
    lines = [
        "CUTCTX VERIFY",
        f"Git SHA: {report['git_sha']}",
        f"Datasets: {', '.join(report['datasets'])}",
        f"Compressors: {', '.join(report['compressors'])}",
        f"Status: {status}",
        "",
        f"Passed: {report['summary']['passed']}  Failed: {report['summary']['failed']}  Skipped: {report['summary']['skipped']}",
        f"Tokens saved: {report['summary']['tokens_saved']:,}",
        f"Duration: {report['summary']['duration_ms']:.2f} ms",
        "",
    ]
    for row in report["results"]:
        lines.append(
            f"{row['status']:4s} {row['dataset']:<20s} {row['compressor']:<16s} "
            f"ratio={row['compression_ratio']:.3f} f1={row['f1'] if row['f1'] is not None else '—'} "
            f"irecall={row['information_recall'] if row['information_recall'] is not None else '—'} "
            f"vfidelity={row['verbatim_fidelity'] if row['verbatim_fidelity'] is not None else '—'} "
            f"tps={row['tokens_per_second'] if row['tokens_per_second'] is not None else '—'} "
            f"latency={row['latency_ms']:.2f}ms"
        )
        if row["reasons"]:
            lines.append(f"    reasons: {', '.join(row['reasons'])}")
    return "\n".join(lines)


def _render_verify_markdown(report: dict[str, Any]) -> str:
    """Render a Markdown verification report."""
    lines = [
        "# Cutctx Verify Report",
        "",
        f"Git SHA: `{report['git_sha']}`",
        f"Status: **{'PASS' if report['pass'] else 'FAIL'}**",
        f"Datasets: {', '.join(report['datasets'])}",
        f"Compressors: {', '.join(report['compressors'])}",
        "",
        "## Thresholds",
        "",
        f"- F1 >= {report['thresholds']['min_f1']:.2f}",
        f"- Information recall >= {report['thresholds']['min_information_recall']:.2f}",
        f"- Critical item recall >= {report['thresholds']['min_critical_item_recall']:.2f}",
        f"- Verbatim fidelity >= {report['thresholds']['min_verbatim_fidelity']:.2f}",
        f"- Tokens / second >= {report['thresholds']['min_tokens_per_second']:.1f}",
        f"- Compression ratio <= {report['thresholds']['max_compression_ratio']:.2f}",
        f"- Latency <= {report['thresholds']['max_latency_ms']:.0f} ms",
        "",
        "## Results",
        "",
        "| Dataset | Compressor | Tokens Saved | Compression Ratio | F1 | Information Recall | Critical Item Recall | Verbatim Fidelity | Tokens / Second | Latency ms | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["results"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["dataset"],
                    row["compressor"],
                    f"{row['tokens_saved']:,}",
                    f"{row['compression_ratio']:.3f}",
                    f"{row['f1']:.3f}" if row["f1"] is not None else "—",
                    f"{row['information_recall']:.3f}"
                    if row["information_recall"] is not None
                    else "—",
                    f"{row['critical_item_recall']:.3f}"
                    if row["critical_item_recall"] is not None
                    else "—",
                    f"{row['verbatim_fidelity']:.3f}"
                    if row["verbatim_fidelity"] is not None
                    else "—",
                    f"{row['tokens_per_second']:.1f}"
                    if row["tokens_per_second"] is not None
                    else "—",
                    f"{row['latency_ms']:.2f}",
                    row["status"],
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"Summary: {report['summary']['passed']} passed, {report['summary']['failed']} failed, {report['summary']['skipped']} skipped.",
        ]
    )
    if report["skipped_compressors"]:
        lines.append(f"Skipped compressors: {', '.join(report['skipped_compressors'])}")
    return "\n".join(lines)
