"""Evaluation CLI commands."""

from __future__ import annotations

import time as time_module
from collections.abc import Callable
from pathlib import Path

import click

from .main import main


@main.group()
def evals() -> None:
    """Memory evaluation and compressor benchmark commands.

    \b
    Examples:
        cutctx evals memory       Run LoCoMo memory evaluation
        cutctx evals memory-v2    Run V2 evaluation with LLM-controlled tools
        cutctx evals benchmark    Run cross-compressor benchmark (ratio, F1, ROUGE-L)
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
            "smart_crusher",
            "log",
            "search",
            "diff",
            "code",
            "kompress",
            "llmlingua",
            "drain3",
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
            "f1",
            "rouge_l",
            "information_recall",
            "exact_match",
        ]
    ),
    default=["ratio", "f1", "information_recall"],
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
@click.option("--seed", type=int, default=42)
@click.option(
    "--publish",
    is_flag=True,
    default=False,
    help="Append this run's results to docs/benchmarks.md (idempotent per day).",
)
def benchmark(
    dataset: tuple[str, ...],
    longbench_task: str,
    n_samples: int,
    compressors: tuple[str, ...],
    metrics: tuple[str, ...],
    parallel: int,
    output: str | None,
    markdown: bool,
    seed: int,
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
    _run_benchmark(
        datasets=list(dataset),
        longbench_task=longbench_task,
        n_samples=n_samples,
        compressors=list(compressors),
        metrics=list(metrics),
        parallel=parallel,
        output=output,
        markdown=markdown,
        seed=seed,
        publish=publish,
    )


main.add_command(benchmark, name="benchmark")


# -----------------------------------------------------------------------------
# Benchmark implementation
# -----------------------------------------------------------------------------


def _run_benchmark(
    *,
    datasets: list[str],
    longbench_task: str,
    n_samples: int,
    compressors: list[str],
    metrics: list[str],
    parallel: int,
    output: str | None,
    markdown: bool,
    seed: int,
    publish: bool,
) -> None:
    """Core benchmark logic."""
    import warnings

    # Suppress noisy UserWarning from optional dependencies
    warnings.filterwarnings("ignore", category=UserWarning)

    from cutctx.evals.benchmark_runner import BenchmarkRunner
    from cutctx.evals.datasets import load_dataset_by_name

    # Print banner
    click.echo(
        f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                    CUTCTX COMPRESSOR BENCHMARK                       ║
║                  Reproducible Cross-Compressor Comparison               ║
╚═══════════════════════════════════════════════════════════════════════╝

Configuration:
  Datasets:         {", ".join(datasets)}
  Samples/dataset:  {n_samples}
  Compressors:      {", ".join(compressors) if "all" not in compressors else "all available"}
  Metrics:          {", ".join(metrics)}
  Parallelism:      {parallel} workers
  Seed:             {seed}
"""
    )

    runner = BenchmarkRunner()

    # Resolve compressor selection
    all_comp_keys = sorted(runner._adapters.keys()) if hasattr(runner, "_adapters") else [a.name for a in runner.list_compressors()]
    if "all" in compressors:
        selected_compressors = all_comp_keys
    else:
        selected_compressors = compressors

    # Warn about missing optional compressors
    adapters = {a.name: a for a in runner.list_compressors()}
    for comp_key in selected_compressors:
        adapter = adapters.get(comp_key)
        if adapter and not adapter.available:
            click.echo(f"  ⚠  Compressor '{comp_key}' not available (install optional deps)")
    click.echo("")

    # Expand "all" datasets if needed
    if "all" in datasets:
        from cutctx.evals.datasets import list_available_datasets

        by_cat = list_available_datasets()
        datasets = [ds for cat_list in by_cat.values() for ds in cat_list]

    # Accumulate results across datasets
    all_results = []
    all_datasets = []
    total_start = time_module.time()

    for ds_name in datasets:
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
            metrics=metrics,
            n=n_actual,
            parallel=parallel,
            seed=seed,
        )

        all_results.extend(suite_result.results)
        all_datasets.append(suite.name)

    total_duration = time_module.time() - total_start

    # Build final result
    from cutctx.evals.benchmark_report import BenchmarkSuiteResult

    final = BenchmarkSuiteResult(
        seed=seed,
        compressors=selected_compressors,
        datasets=all_datasets,
        results=all_results,
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
            md_content = _build_markdown_report(final, metrics)
            Path(md_path).write_text(md_content, encoding="utf-8")
            click.echo(f"Markdown saved to: {md_path}")

    # Publish: append a dated section to docs/benchmarks.md
    if publish:
        publish_content = md_content if markdown else _build_markdown_report(final, metrics)
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
        click.echo(f"    {emoji} {r.compressor:20s}  {ratio_pct:>8s}  ({r.tokens_saved:,} tokens saved)")

    # Print metric tables for F1 / IR
    for metric in ("f1", "information_recall"):
        vals = [
            (r.compressor, getattr(r, metric))
            for r in active
            if getattr(r, metric) is not None
        ]
        if vals:
            label = {"f1": "F1 Score", "information_recall": "Information Recall"}.get(
                metric, metric
            )
            click.echo(f"\n  {label}:")
            for comp_name, val in vals:
                click.echo(f"    {comp_name:20s}  {val:.3f}")


def _build_markdown_report(
    result: BenchmarkSuiteResult, metrics: list[str]
) -> str:
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
        lines.append("")
    lines.append(
        "_Generated by `cutctx evals benchmark`_"
    )
    return "\n".join(lines)


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
    existing = docs_path.read_text(encoding="utf-8") if docs_path.exists() else "# Cutctx Benchmarks\n"
    if heading in existing:
        before, _, after = existing.partition(heading)
        next_idx = after.find("\n## `cutctx evals benchmark` — ")
        rest = after[next_idx:] if next_idx != -1 else ""
        existing = before + section + rest
    else:
        existing = existing.rstrip("\n") + "\n\n" + section
    docs_path.write_text(existing, encoding="utf-8")
    click.echo(f"Published results to: {docs_path}")

