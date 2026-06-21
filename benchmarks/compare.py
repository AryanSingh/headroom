#!/usr/bin/env python3
"""
Tool comparison benchmark.

Compare compression quality and performance across Cutctx, LLMLingua2, Morph, and others.

Usage:
    # Compare headroom and llmlingua2 on ToolBench
    python compare.py --tool headroom --tool llmlingua2 --corpus toolbench

    # Dry run with synthetic data
    python compare.py --tool headroom --tool llmlingua2 --dry-run

    # Multi-corpus comparison
    python compare.py --tool headroom --corpus toolbench --corpus longbench

    # Save results
    python compare.py --tool headroom --tool llmlingua2 --output results.json

Available corpora:
    - synthetic: Generated data (no downloads)
    - toolbench: Tool use benchmarks (JSON + queries)
    - longbench: Long document understanding
    - mixed: Combination of above

Available tools:
    - headroom: Content-aware compression
    - llmlingua2: LLM-based importance scoring
    - morph: Token-level deletion
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tiktoken

# Cutctx
try:
    from headroom import compress
    HEADROOM_AVAILABLE = True
except ImportError:
    HEADROOM_AVAILABLE = False

# LLMLingua2
try:
    from llmlingua import PromptCompressor
    LLMLINGUA2_AVAILABLE = True
except ImportError:
    LLMLINGUA2_AVAILABLE = False

# Morph (hypothetical API)
try:
    from morph import compress as morph_compress
    MORPH_AVAILABLE = True
except ImportError:
    MORPH_AVAILABLE = False


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result from comparing tools on a single corpus."""
    tool: str
    corpus: str
    input_tokens: int
    output_tokens: int
    compression_ratio: float  # 1 - (output / input)
    latency_ms: float
    throughput_tokens_per_sec: float
    model_size_mb: float = 0.0
    memory_rss_mb: float = 0.0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.error is None:
            del data["error"]
        return data


# =============================================================================
# CORPUS LOADERS
# =============================================================================

def load_synthetic_corpus(corpus_type: str) -> str:
    """Generate synthetic test data for a corpus type."""
    if corpus_type == "toolbench":
        # Simulate tool use: tool descriptions + API responses
        tools = [
            {
                "name": f"tool_{i}",
                "description": f"Tool for doing something with {i}",
                "params": [f"param_{j}" for j in range(3)],
            }
            for i in range(20)
        ]

        results = [
            {
                "status": "success",
                "data": [{"id": j, "value": j * 100} for j in range(10)],
                "metadata": {"timestamp": "2026-06-15T10:30:00Z"},
            }
            for _ in range(5)
        ]

        return json.dumps(
            {"tools": tools, "results": results},
            indent=2,
        )

    elif corpus_type == "longbench":
        # Simulate long document QA
        document = " ".join([
            f"Section {i}: " + " ".join([
                f"The quick brown fox jumps over the lazy dog {i}_{j}. "
                for j in range(50)
            ])
            for i in range(10)
        ])
        return document

    elif corpus_type == "mixed":
        # Mix of structured and prose
        structured = json.dumps(
            {"data": [{"id": i, "value": i * 10} for i in range(100)]},
            indent=2,
        )
        prose = " ".join([
            f"Information about topic {i}: " + " ".join([
                f"word_{j} " for j in range(50)
            ])
            for i in range(5)
        ])
        return structured + "\n\n" + prose

    else:  # generic synthetic
        return "The quick brown fox jumps. " * 1000


def load_corpus(corpus_type: str, corpus_dir: Path, dry_run: bool) -> str:
    """Load a corpus (synthetic or real)."""
    if dry_run:
        return load_synthetic_corpus(corpus_type)

    # Try to load from disk
    corpus_path = corpus_dir / corpus_type
    if not corpus_path.exists():
        logger.warning(f"Corpus {corpus_path} not found, using synthetic data")
        return load_synthetic_corpus(corpus_type)

    # Load from disk (implementation depends on format)
    if corpus_path.is_file() and corpus_path.suffix == ".jsonl":
        text_parts = []
        with open(corpus_path) as f:
            for line in f:
                try:
                    item = json.loads(line)
                    text_parts.append(json.dumps(item))
                except json.JSONDecodeError:
                    text_parts.append(line.strip())
        return "\n".join(text_parts)

    elif corpus_path.is_dir():
        # Concatenate all text files
        text_parts = []
        for file in corpus_path.glob("*"):
            if file.suffix in (".txt", ".json", ".jsonl"):
                with open(file) as f:
                    text_parts.append(f.read())
        return "\n\n".join(text_parts)

    else:
        with open(corpus_path) as f:
            return f.read()


# =============================================================================
# COMPRESSION TOOLS
# =============================================================================

class CompressionTool:
    """Base class for compression tool wrappers."""

    def compress(self, text: str) -> tuple[str, float]:
        """Compress text.

        Returns:
            (compressed_text, latency_ms)
        """
        raise NotImplementedError

    def get_metrics(self) -> dict[str, Any]:
        """Get tool-specific metrics (model size, memory, etc)."""
        return {}


class CutctxTool(CompressionTool):
    """Wrapper for Cutctx compression."""

    def __init__(self):
        if not HEADROOM_AVAILABLE:
            raise ImportError("headroom not installed")
        self.compress_func = compress

    def compress(self, text: str) -> tuple[str, float]:
        start = time.perf_counter()
        result = self.compress_func(text)
        latency = (time.perf_counter() - start) * 1000
        return result.compressed_text, latency

    def get_metrics(self) -> dict[str, Any]:
        return {
            "model_size_mb": 280,  # Kompress v2 int8
            "framework": "ONNX + Rust",
        }


class LLMLingua2Tool(CompressionTool):
    """Wrapper for LLMLingua2 compression."""

    def __init__(self):
        if not LLMLINGUA2_AVAILABLE:
            raise ImportError("llmlingua2 not installed")
        self.compressor = PromptCompressor(model_name="microsoft/phi-2")

    def compress(self, text: str) -> tuple[str, float]:
        start = time.perf_counter()
        compressed = self.compressor.compress_prompt(text, target_token=None)
        latency = (time.perf_counter() - start) * 1000
        return compressed, latency

    def get_metrics(self) -> dict[str, Any]:
        return {
            "model_size_mb": 4200,  # Approximate
            "framework": "PyTorch",
        }


class MorphTool(CompressionTool):
    """Wrapper for Morph compression (placeholder)."""

    def __init__(self):
        if not MORPH_AVAILABLE:
            raise ImportError("morph not installed")

    def compress(self, text: str) -> tuple[str, float]:
        raise NotImplementedError("Morph API not fully implemented")


TOOLS: dict[str, Callable[[], CompressionTool]] = {
    "cutctx": CutctxTool,
    "llmlingua2": LLMLingua2Tool,
    "morph": MorphTool,
}


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def benchmark_tool(
    tool: CompressionTool,
    tool_name: str,
    text: str,
    corpus_name: str,
    verbose: bool = False,
) -> ComparisonResult | None:
    """Run benchmark for a single tool on a corpus.

    Args:
        tool: Compression tool instance
        tool_name: Name of tool
        text: Input text
        corpus_name: Name of corpus
        verbose: Print details

    Returns:
        ComparisonResult or None if failed
    """
    enc = tiktoken.get_encoding("cl100k_base")
    input_tokens = len(enc.encode(text))

    if input_tokens == 0:
        logger.warning(f"{tool_name}: Empty input")
        return None

    try:
        compressed_text, latency = tool.compress(text)
        output_tokens = len(enc.encode(compressed_text))
    except Exception as e:
        logger.error(f"{tool_name} failed: {e}")
        return ComparisonResult(
            tool=tool_name,
            corpus=corpus_name,
            input_tokens=input_tokens,
            output_tokens=input_tokens,
            compression_ratio=0.0,
            latency_ms=0.0,
            throughput_tokens_per_sec=0.0,
            success=False,
            error=str(e),
        )

    compression_ratio = 1.0 - (output_tokens / input_tokens)
    throughput = (output_tokens / latency * 1000) if latency > 0 else 0.0

    result = ComparisonResult(
        tool=tool_name,
        corpus=corpus_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        compression_ratio=compression_ratio,
        latency_ms=latency,
        throughput_tokens_per_sec=throughput,
    )

    # Add tool-specific metrics
    metrics = tool.get_metrics()
    if "model_size_mb" in metrics:
        result.model_size_mb = metrics["model_size_mb"]

    if verbose:
        logger.info(
            f"{tool_name}/{corpus_name}: {input_tokens:,} -> {output_tokens:,} "
            f"({compression_ratio:.1%}, {latency:.1f}ms)"
        )

    return result


def print_comparison_table(results: list[ComparisonResult]) -> None:
    """Print formatted comparison table."""
    print("\n" + "=" * 100)
    print("Compression Comparison Results")
    print("=" * 100)

    # Group by corpus
    by_corpus: dict[str, list[ComparisonResult]] = {}
    for result in results:
        if result.corpus not in by_corpus:
            by_corpus[result.corpus] = []
        by_corpus[result.corpus].append(result)

    for corpus_name in sorted(by_corpus.keys()):
        corpus_results = by_corpus[corpus_name]
        print(f"\n{corpus_name.upper()}")
        print("-" * 100)
        print("{:<20} {:<12} {:<12} {:<12} {:<10} {:<15}".format(
            "Tool", "Input Tokens", "Output Tokens", "Ratio", "Latency", "Throughput"
        ))
        print("-" * 100)

        for result in sorted(corpus_results, key=lambda r: -r.compression_ratio):
            if result.success:
                print(f"{result.tool:<20} {result.input_tokens:<12,} {result.output_tokens:<12,} {result.compression_ratio:<11.1%} {result.latency_ms:<9.1f}ms {result.throughput_tokens_per_sec:<14,.0f}")
            else:
                print(f"{result.tool:<20} ERROR: {result.error}")

    print("=" * 100)


def main() -> int:
    """Main comparison runner."""
    parser = argparse.ArgumentParser(
        description="Compare compression tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--tool",
        action="append",
        default=[],
        help="Tools to compare (default: headroom). Can specify multiple times.",
    )

    parser.add_argument(
        "--corpus",
        action="append",
        default=[],
        help="Corpora to test (default: synthetic). Can specify multiple times.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic data (no corpus download)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Save JSON results to file",
    )

    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path(__file__).parent / "corpora",
        help="Corpus directory (default: ./corpora/)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Defaults
    tools = args.tool or ["cutctx"]
    corpora = args.corpus or ["synthetic"]

    logger.info("=" * 70)
    logger.info("Tool Comparison Benchmark")
    logger.info(f"Tools: {', '.join(tools)}")
    logger.info(f"Corpora: {', '.join(corpora)}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 70)

    # Initialize tools
    tool_instances: dict[str, CompressionTool] = {}
    for tool_name in tools:
        if tool_name not in TOOLS:
            logger.error(f"Unknown tool: {tool_name}")
            logger.info(f"Available: {', '.join(TOOLS.keys())}")
            return 1

        try:
            tool_class = TOOLS[tool_name]
            tool_instances[tool_name] = tool_class()
            logger.info(f"Loaded tool: {tool_name}")
        except ImportError as e:
            logger.error(f"Cannot load {tool_name}: {e}")
            return 1

    # Run benchmarks
    results = []
    for corpus_name in corpora:
        logger.info(f"Loading corpus: {corpus_name}")
        try:
            text = load_corpus(corpus_name, args.corpus_dir, args.dry_run)
            if not text.strip():
                logger.warning(f"Empty corpus: {corpus_name}")
                continue
        except Exception as e:
            logger.error(f"Failed to load {corpus_name}: {e}")
            continue

        for tool_name, tool in tool_instances.items():
            logger.info(f"Benchmarking {tool_name} on {corpus_name}...")
            result = benchmark_tool(
                tool, tool_name, text, corpus_name, verbose=args.verbose
            )
            if result:
                results.append(result)

    if not results:
        logger.error("No benchmarks completed")
        return 1

    # Print summary
    print_comparison_table(results)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "tools": tools,
            "corpora": corpora,
            "dry_run": args.dry_run,
            "results": [r.to_dict() for r in results],
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
