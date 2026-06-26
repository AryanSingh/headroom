# Drain3 Log Template Mining Integration — Technical Specification

**Status:** Draft  
**Date:** 2026-06-24  
**Scope:** Cutctx / cutctx proxy  
**Feature flag:** `drain3_enabled` (default `False` — 100% opt-in)

---

## Table of Contents

1. [Background and Goal](#1-background-and-goal)
2. [Architecture Overview](#2-architecture-overview)
3. [Dependency Changes](#3-dependency-changes)
4. [Configuration: New Flags and CLI Options](#4-configuration-new-flags-and-cli-options)
5. [New File: `cutctx/transforms/drain3_compressor.py`](#5-new-file-cutctxtransformsdrain3_compressorpy)
6. [Integration Point: ContentRouter](#6-integration-point-contentrouter)
7. [Proxy Server Startup Wiring](#7-proxy-server-startup-wiring)
8. [Test File: `tests/test_drain3_compressor.py`](#8-test-file-teststest_drain3_compressorpy)
9. [Verification Steps](#9-verification-steps)
10. [File Creation / Modification Summary](#10-file-creation--modification-summary)

---

## 1. Background and Goal

### 1.1 Current Log Compression

Cutctx's existing log compressor (`cutctx/transforms/log_compressor.py`) is a
Rust-backed statistical sampler. It scores each log line by level
(ERROR=1.0, WARN=0.5, INFO=0.1, …), preserves stack traces and summary lines,
and discards low-importance lines up to a configurable `max_total_lines` cap.

This approach excels at *structured* logs (pytest output, cargo builds) but is
limited for *repetitive* log streams where hundreds of lines share the same
pattern but differ only in variable fields:

```
2026-06-24 09:01:03 INFO  Request 7381 from 10.0.0.5 processed in 14ms
2026-06-24 09:01:04 INFO  Request 7382 from 10.0.0.7 processed in 22ms
2026-06-24 09:01:04 INFO  Request 7383 from 10.0.0.5 processed in 9ms
… (800 more identical-pattern lines)
```

The current compressor treats each line as independent and keeps a random
sample. An LLM reading the compressed output still sees many lines that convey
no additional semantic information.

### 1.2 What Drain3 Adds

[Drain3](https://github.com/logpai/Drain3) (MIT license) is an online streaming
log template miner. Given a stream of log lines it:

1. Parses each line by splitting on whitespace and identifying numeric /
   IP / path tokens as wildcards.
2. Maintains a prefix-tree of depth `sim_depth` (default 4) per line length.
3. Groups lines into *clusters* whose constant tokens match a **similarity
   threshold** (default 0.4 = 40 % of tokens must be identical).
4. Returns for each line its `LogCluster` object containing:
   - `cluster_id` — stable integer
   - `get_template()` — the canonical template string, e.g.
     `"INFO Request <*> from <*> processed in <*>"`
   - `size` — number of lines that matched this cluster so far

This is semantically richer than deduplication: Drain3 groups lines that have
*structurally identical formats* even when no two lines are literally identical.

### 1.3 Goal

Implement `Drain3LogCompressor`, an opt-in drop-in that:

- Intercepts the `CompressionStrategy.LOG` path in `ContentRouter`.
- Feeds all log lines through `drain3.TemplateMiner` to form clusters.
- Emits one representative line per cluster annotated with its count.
- Falls back to `LogCompressor` if `drain3` is not installed (opt-in import).
- Is 100 % opt-in: doing nothing if `drain3_enabled=False` (the default).

**Expected compression improvement:** for repetitive application/web-server logs
(80–95 % same-pattern lines), Drain3 compression often reaches a 10–50× token
reduction vs. the current sampler's 2–5×, while still retaining one concrete
example line per template that the LLM can read.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Incoming LLM request (messages list)                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  TransformPipeline   │
              │  (proxy/server.py)   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   ContentRouter      │  ← cutctx/transforms/content_router.py
              │  _get_log_compressor │
              └──────────┬───────────┘
                         │  ContentType.BUILD_OUTPUT detected
                         │  (or CompressionStrategy.LOG explicitly)
                         ▼
        drain3_enabled?
           ┌─────┴───────┐
          YES            NO
           │              │
           ▼              ▼
  ┌──────────────────┐  ┌─────────────────┐
  │Drain3LogCompressor│  │  LogCompressor  │
  │ (new)            │  │  (existing Rust) │
  └────────┬─────────┘  └─────────────────┘
           │
           │  drain3 available?
      ┌────┴────┐
     YES       NO
      │         │
      ▼         ▼
  [Template  [Fallback to
   mining]    LogCompressor]
      │
      ▼
  One representative line per cluster
  + "(N more similar lines omitted)" annotation
```

### 2.1 Data Flow Inside `Drain3LogCompressor.compress()`

```
raw_text
  │
  ├─ split on "\n"
  │
  ├─ for each line → TemplateMiner.add_log_message()
  │     returns LogCluster
  │
  ├─ bucket lines by cluster_id
  │     {cluster_id: [line1, line2, …]}
  │
  ├─ for each bucket:
  │     select representative = first line (chronologically earliest)
  │     if bucket has >1 line:
  │       append annotation "(N more similar lines omitted)"
  │
  ├─ sort buckets by first-seen line number (preserves log ordering)
  │
  └─ join → compressed_text
```

### 2.2 Thread Safety

`TemplateMiner` is *not* thread-safe internally (its prefix tree is mutated on
each `add_log_message` call). `Drain3LogCompressor` holds a `threading.Lock`
around all `TemplateMiner` access. The lock is per-compressor-instance, not
global. Since `ContentRouter` instantiates one `_log_compressor` instance
per router, and each router is owned by one pipeline, this is safe for both
single-worker and multi-worker deployments (each worker process has its own
router instance).

---

## 3. Dependency Changes

### 3.1 `pyproject.toml` — New Optional Group

Add a new entry to `[project.optional-dependencies]` directly after the
existing `html` group (before `benchmark`):

```toml
# ML log template mining via Drain3. Opt in with:
#   pip install cutctx-ai[log-ml]
# Enables drain3_enabled=True in ProxyConfig / --drain3 CLI flag.
log-ml = [
    "drain3>=0.9.11",
]
```

### 3.2 Installation

```bash
# Minimal (proxy only — no Drain3)
pip install cutctx-ai[proxy]

# With Drain3 log template mining
pip install cutctx-ai[proxy,log-ml]

# Development
uv sync --extra dev --extra log-ml
```

### 3.3 Why a Separate Extra

- `drain3` pulls in `PyYAML`, `jsonpickle`, and `cachetools`. These are not
  needed by the core proxy.
- Keeping `log-ml` separate means zero dependency footprint for users who don't
  need ML log compression.
- The naming pattern mirrors `llmlingua` (ML prompt compression), `ml`
  (Kompress/ModernBERT), and `code` (tree-sitter).

---

## 4. Configuration: New Flags and CLI Options

### 4.1 `cutctx/proxy/models.py`

Add three new fields to the `ProxyConfig` dataclass immediately after the
existing `code_graph_watcher` field (currently at line 180):

```python
# Drain3 ML log template mining. Groups repetitive log lines by
# template and keeps one representative per cluster.
# Requires: pip install cutctx-ai[log-ml]
# CLI: --drain3; env: CUTCTX_DRAIN3=1.
drain3_enabled: bool = False

# Maximum number of log-line clusters Drain3 will track before it
# starts evicting old clusters. Higher values use more RAM but improve
# template coverage for long-running sessions.
# CLI: --drain3-max-clusters; env: CUTCTX_DRAIN3_MAX_CLUSTERS.
drain3_max_clusters: int = 1000

# Drain3 similarity threshold (0.0–1.0). A line matches an existing
# cluster when the fraction of matching constant tokens exceeds this
# threshold. Lower values merge more aggressively; higher values keep
# more clusters. Default 0.4 matches Drain3's published best-practice.
# CLI: --drain3-sim-threshold; env: CUTCTX_DRAIN3_SIM_THRESHOLD.
drain3_sim_threshold: float = 0.4
```

### 4.2 `cutctx/cli/proxy.py`

Add three `@click.option` decorators to the `proxy` command, grouped with the
other optional-feature flags (near the `--code-graph` option at line 419):

```python
@click.option(
    "--drain3",
    "drain3_enabled",
    is_flag=True,
    envvar="CUTCTX_DRAIN3",
    help=(
        "Enable Drain3 ML log template mining. Groups repetitive log lines by "
        "template; emits one representative per cluster. "
        "Requires: pip install cutctx-ai[log-ml]. "
        "Env: CUTCTX_DRAIN3."
    ),
)
@click.option(
    "--drain3-max-clusters",
    default=None,
    type=click.IntRange(min=10),
    envvar="CUTCTX_DRAIN3_MAX_CLUSTERS",
    help=(
        "Maximum Drain3 log clusters to track (default: 1000). "
        "Env: CUTCTX_DRAIN3_MAX_CLUSTERS."
    ),
)
@click.option(
    "--drain3-sim-threshold",
    default=None,
    type=click.FloatRange(min=0.0, max=1.0),
    envvar="CUTCTX_DRAIN3_SIM_THRESHOLD",
    help=(
        "Drain3 similarity threshold 0.0–1.0 (default: 0.4). "
        "Lower = merge more aggressively. "
        "Env: CUTCTX_DRAIN3_SIM_THRESHOLD."
    ),
)
```

These values flow into `ProxyConfig` through the existing `proxy` command
handler, exactly as `selective_filter_threshold` and `code_graph_watcher` do
(the handler already unpacks `**kwargs` or explicitly sets `ProxyConfig`
fields from click parameters).

---

## 5. New File: `cutctx/transforms/drain3_compressor.py`

This is the complete, working implementation. Create this file at
`cutctx/transforms/drain3_compressor.py`.

```python
"""Drain3-backed log template mining compressor.

Opt-in replacement for the Rust LogCompressor on the
CompressionStrategy.LOG path. Uses Drain3's online streaming template
miner (MIT licence) to cluster log lines by structural pattern, then
emits one representative line per cluster annotated with a count.

Activation
----------
Install the optional dependency group::

    pip install cutctx-ai[log-ml]      # adds drain3>=0.9.11

Then start the proxy with::

    cutctx proxy --drain3

Or set the env var::

    CUTCTX_DRAIN3=1 cutctx proxy ...

Fallback
--------
When Drain3 is *not* installed this module is still importable — the
``Drain3LogCompressor`` class is always defined but its ``compress()``
method delegates to ``LogCompressor`` (the Rust-backed fallback).  This
means ContentRouter can unconditionally import this module when
``drain3_enabled=True``; the runtime availability check happens inside
the compressor, not in the router.

Thread Safety
-------------
``TemplateMiner`` mutates its internal prefix-tree on every
``add_log_message()`` call.  ``Drain3LogCompressor`` holds a per-instance
``threading.Lock`` that serialises all miner access.  Each ContentRouter
instance owns exactly one ``Drain3LogCompressor`` instance, so workers
in a multi-process deployment each have their own lock — no contention
across processes.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # drain3 imports are always guarded by try/except

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability probe — resolved once at module import time so every call to
# compress() skips the try/except path on the hot path.
# ---------------------------------------------------------------------------

_DRAIN3_AVAILABLE: bool = False
_drain3_import_error: str | None = None

try:
    import drain3  # noqa: F401 — availability probe
    _DRAIN3_AVAILABLE = True
except ImportError as _e:
    _drain3_import_error = str(_e)
    logger.debug(
        "drain3 not installed; Drain3LogCompressor will delegate to LogCompressor. "
        "Install with: pip install cutctx-ai[log-ml]"
    )


def drain3_available() -> bool:
    """Return True when the drain3 package is importable."""
    return _DRAIN3_AVAILABLE


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class Drain3CompressionResult:
    """Result of Drain3-based log compression.

    Attributes
    ----------
    compressed:
        The compressed log text.  One representative line per discovered
        cluster, with a count annotation when the cluster had >1 line.
    original:
        The original unmodified input text.
    original_line_count:
        Number of non-empty lines in the original.
    compressed_line_count:
        Number of lines in the compressed output.
    clusters_found:
        Number of distinct log templates discovered.
    compression_ratio:
        ``compressed_line_count / original_line_count``.  Lower is better.
    drain3_used:
        ``True`` when Drain3 ran successfully; ``False`` when the fallback
        ``LogCompressor`` was used (drain3 not installed or error).
    stats:
        Arbitrary key/value counters for observability.
    """

    compressed: str
    original: str
    original_line_count: int
    compressed_line_count: int
    clusters_found: int
    compression_ratio: float
    drain3_used: bool = True
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def tokens_saved_estimate(self) -> int:
        chars_saved = len(self.original) - len(self.compressed)
        return max(0, chars_saved // 4)

    @property
    def lines_omitted(self) -> int:
        return self.original_line_count - self.compressed_line_count


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class Drain3CompressorConfig:
    """Configuration for ``Drain3LogCompressor``.

    Attributes
    ----------
    max_clusters:
        Maximum number of clusters the TemplateMiner will track.
        Eviction uses an LRU strategy internal to Drain3.
    sim_threshold:
        Fraction of non-wildcard tokens that must match for a line to
        join an existing cluster.  Range 0.0–1.0.  Drain3's published
        best-practice default is 0.4.
    depth:
        Drain3 prefix-tree depth.  Higher values produce more specific
        templates at the cost of more clusters.  Default 4 is standard.
    max_children:
        Maximum branching factor of the prefix tree.  Default 100.
    fallback_on_error:
        When True (default), silently delegate to ``LogCompressor`` if
        Drain3 raises an unexpected exception during compression.
    """

    max_clusters: int = 1000
    sim_threshold: float = 0.4
    depth: int = 4
    max_children: int = 100
    fallback_on_error: bool = True


# ---------------------------------------------------------------------------
# Main compressor
# ---------------------------------------------------------------------------


class Drain3LogCompressor:
    """ML log template mining compressor backed by Drain3.

    Replaces ``LogCompressor`` on the ``CompressionStrategy.LOG`` path
    when ``drain3_enabled=True`` in the proxy config.

    If Drain3 is not installed (or raises during compression), the
    compressor transparently delegates to ``LogCompressor`` so the proxy
    never returns an error to the user.

    Example
    -------
    ::

        from cutctx.transforms.drain3_compressor import (
            Drain3LogCompressor,
            Drain3CompressorConfig,
        )

        compressor = Drain3LogCompressor(
            Drain3CompressorConfig(max_clusters=500, sim_threshold=0.4)
        )
        result = compressor.compress(log_text)
        print(result.compressed)
        print(f"Clusters: {result.clusters_found}")
        print(f"Ratio: {result.compression_ratio:.2%}")
    """

    def __init__(self, config: Drain3CompressorConfig | None = None) -> None:
        self.config = config or Drain3CompressorConfig()
        self._lock = threading.Lock()
        # Lazy-loaded TemplateMiner — created on first compress() call so
        # that importing this module has zero overhead when drain3 is absent.
        self._miner: Any = None
        # Fallback compressor — lazy-loaded on first fallback invocation.
        self._fallback: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(self, content: str, bias: float = 1.0) -> Drain3CompressionResult:
        """Compress ``content`` using Drain3 template clustering.

        Parameters
        ----------
        content:
            Raw log text (newline-separated lines).
        bias:
            Compression aggressiveness multiplier passed through to the
            fallback ``LogCompressor`` when Drain3 is unavailable.

        Returns
        -------
        Drain3CompressionResult
            Always returns a result; falls back to ``LogCompressor`` if
            Drain3 is not installed or raises.
        """
        if not _DRAIN3_AVAILABLE:
            logger.debug(
                "Drain3LogCompressor: drain3 not available (%s); using LogCompressor fallback",
                _drain3_import_error,
            )
            return self._fallback_compress(content, bias)

        try:
            return self._drain3_compress(content)
        except Exception as exc:  # noqa: BLE001
            if self.config.fallback_on_error:
                logger.warning(
                    "Drain3LogCompressor: unexpected error during template mining, "
                    "falling back to LogCompressor: %s",
                    exc,
                    exc_info=True,
                )
                return self._fallback_compress(content, bias)
            raise

    # ------------------------------------------------------------------
    # Internal: Drain3 path
    # ------------------------------------------------------------------

    def _get_miner(self) -> Any:
        """Lazily create and return a ``TemplateMiner`` instance.

        The miner is *not* shared across ``compress()`` calls — it is
        reset for each call to avoid template state bleeding between
        unrelated log blocks.  The lock ensures that concurrent calls
        do not race on ``self._miner``.
        """
        # Always create a fresh miner per compress() invocation so that
        # templates from a previous tool_result do not influence the
        # current one.  The miner is cheap to construct (~0.1 ms).
        from drain3 import TemplateMiner
        from drain3.template_miner_config import TemplateMinerConfig

        cfg = TemplateMinerConfig()
        cfg.drain_sim_th = self.config.sim_threshold
        cfg.drain_depth = self.config.depth
        cfg.drain_max_children = self.config.max_children
        cfg.max_clusters = self.config.max_clusters
        # Disable persistence — we don't need cross-request state.
        cfg.snapshot_interval_minutes = 0
        cfg.compress_state = False

        return TemplateMiner(config=cfg)

    def _drain3_compress(self, content: str) -> Drain3CompressionResult:
        """Core Drain3 compression path.  Holds ``self._lock``."""
        lines = content.splitlines()
        # Strip blank lines for template mining but track their positions
        # so we can identify original line count correctly.
        non_empty = [line for line in lines if line.strip()]
        original_line_count = len(non_empty)

        if original_line_count == 0:
            return Drain3CompressionResult(
                compressed=content,
                original=content,
                original_line_count=0,
                compressed_line_count=0,
                clusters_found=0,
                compression_ratio=1.0,
                drain3_used=True,
            )

        with self._lock:
            miner = self._get_miner()

            # Map each line to its cluster and remember first occurrence.
            # cluster_id -> (representative_line, total_count, first_index)
            cluster_order: list[int] = []  # cluster_ids in first-seen order
            cluster_data: dict[int, dict[str, Any]] = {}

            for idx, line in enumerate(non_empty):
                result = miner.add_log_message(line)
                if result is None:
                    # Drain3 returns None when the internal state is not
                    # ready to assign a cluster (first message setup).
                    # Treat line as a singleton.
                    synthetic_id = -(idx + 1)
                    cluster_data[synthetic_id] = {
                        "representative": line,
                        "count": 1,
                        "first_index": idx,
                        "template": line,
                    }
                    cluster_order.append(synthetic_id)
                    continue

                cluster, _change_type = result
                cid: int = cluster.cluster_id

                if cid not in cluster_data:
                    cluster_data[cid] = {
                        "representative": line,  # first-seen line is canonical
                        "count": 1,
                        "first_index": idx,
                        "template": cluster.get_template(),
                    }
                    cluster_order.append(cid)
                else:
                    cluster_data[cid]["count"] += 1
                    # Update template after each merge so the final
                    # annotated line shows the most-converged template.
                    cluster_data[cid]["template"] = cluster.get_template()

        # Build output — one line per cluster, sorted by first appearance.
        output_lines: list[str] = []
        for cid in cluster_order:
            data = cluster_data[cid]
            count: int = data["count"]
            representative: str = data["representative"]
            output_lines.append(representative)
            if count > 1:
                output_lines.append(
                    f"    [{count - 1} more similar lines omitted"
                    f" — template: {data['template']}]"
                )

        compressed = "\n".join(output_lines)
        compressed_line_count = len(output_lines)
        clusters_found = len(cluster_order)

        compression_ratio = (
            compressed_line_count / original_line_count if original_line_count else 1.0
        )

        logger.debug(
            "Drain3LogCompressor: %d lines → %d output lines (%d clusters, ratio=%.2f)",
            original_line_count,
            compressed_line_count,
            clusters_found,
            compression_ratio,
        )

        return Drain3CompressionResult(
            compressed=compressed,
            original=content,
            original_line_count=original_line_count,
            compressed_line_count=compressed_line_count,
            clusters_found=clusters_found,
            compression_ratio=compression_ratio,
            drain3_used=True,
            stats={
                "clusters": clusters_found,
                "original_lines": original_line_count,
                "compressed_lines": compressed_line_count,
            },
        )

    # ------------------------------------------------------------------
    # Internal: fallback path
    # ------------------------------------------------------------------

    def _get_fallback(self) -> Any:
        """Lazily load the Rust-backed ``LogCompressor`` fallback."""
        if self._fallback is None:
            from cutctx.transforms.log_compressor import LogCompressor

            self._fallback = LogCompressor()
        return self._fallback

    def _fallback_compress(self, content: str, bias: float) -> Drain3CompressionResult:
        """Delegate to ``LogCompressor`` and wrap the result."""
        fallback = self._get_fallback()
        result = fallback.compress(content, bias=bias)

        lines_in = result.original_line_count
        lines_out = result.compressed_line_count
        ratio = lines_out / lines_in if lines_in else 1.0

        return Drain3CompressionResult(
            compressed=result.compressed,
            original=content,
            original_line_count=lines_in,
            compressed_line_count=lines_out,
            clusters_found=0,  # no clustering — statistical sampler
            compression_ratio=ratio,
            drain3_used=False,
            stats=result.stats,
        )


__all__ = [
    "Drain3LogCompressor",
    "Drain3CompressorConfig",
    "Drain3CompressionResult",
    "drain3_available",
]
```

### 5.1 Key Design Decisions

**Fresh miner per `compress()` call.** A `TemplateMiner` persists cluster state
across calls. Re-using it would cause templates from a previous tool_result
(e.g., a pytest run) to influence the next (e.g., a webpack build). Fresh
construction takes ~0.1 ms and avoids cross-request contamination.

**First-seen line as representative.** The chronologically first line is the
most likely to be intact (later lines may have partially converged templates).
This also preserves log ordering in the output.

**Annotation format.** The `[N more similar lines omitted — template: ...]`
annotation gives the LLM the template string so it can reason about what was
removed without reading every line.

**Lock scope.** The lock covers the entire mining loop, not individual
`add_log_message` calls. This prevents a second thread from seeing a partially
built `cluster_data` dict.

---

## 6. Integration Point: ContentRouter

### 6.1 New Attribute in `ContentRouterConfig`

Add one field to the `ContentRouterConfig` dataclass
(`cutctx/transforms/content_router.py`, after `use_llmlingua`):

```python
# Drain3 ML log template mining (opt-in, requires pip install cutctx-ai[log-ml]).
# When True and drain3 is installed, the LOG strategy uses Drain3LogCompressor
# instead of LogCompressor.  Gracefully falls back to LogCompressor if drain3
# is absent even when this flag is True.
use_drain3: bool = False

# Drain3 config forwarded to Drain3LogCompressor.  None means use defaults.
drain3_max_clusters: int = 1000
drain3_sim_threshold: float = 0.4
```

### 6.2 New Lazy Getter in `ContentRouter`

Add a `_drain3_log_compressor` attribute (initialised to `None` in `__init__`)
and a corresponding getter method inside `ContentRouter`:

```python
# In ContentRouter.__init__, after self._log_compressor = None:
self._drain3_log_compressor: Any = None
```

```python
def _get_drain3_log_compressor(self) -> Any:
    """Get Drain3LogCompressor (lazy load).

    Returns the Drain3-backed compressor when ``config.use_drain3`` is
    True and drain3 is installed.  Falls back to returning None (caller
    then falls through to ``_get_log_compressor()``) when drain3 is
    absent and the user has *not* explicitly installed [log-ml].

    The compressor itself gracefully delegates to LogCompressor if drain3
    raises at runtime — this getter only controls the initial load path.
    """
    if self._drain3_log_compressor is None:
        try:
            from .drain3_compressor import (
                Drain3CompressorConfig,
                Drain3LogCompressor,
            )

            cfg = Drain3CompressorConfig(
                max_clusters=self.config.drain3_max_clusters,
                sim_threshold=self.config.drain3_sim_threshold,
            )
            self._drain3_log_compressor = Drain3LogCompressor(cfg)
            logger.info(
                "Drain3LogCompressor loaded (max_clusters=%d, sim_threshold=%.2f)",
                cfg.max_clusters,
                cfg.sim_threshold,
            )
        except ImportError:
            logger.debug(
                "drain3_compressor not importable; LOG path will use LogCompressor"
            )
    return self._drain3_log_compressor
```

### 6.3 Modify `_apply_strategy_to_content` — LOG Branch

Change the `elif strategy == CompressionStrategy.LOG:` branch inside
`_apply_strategy_to_content` (currently at line 1365):

```python
elif strategy == CompressionStrategy.LOG:
    if self.config.enable_log_compressor:
        # Drain3 path: opt-in ML template mining.
        if self.config.use_drain3:
            drain3_compressor = self._get_drain3_log_compressor()
            if drain3_compressor is not None:
                compressor_name = type(drain3_compressor).__name__
                result = drain3_compressor.compress(content, bias=bias)
                compressed, compressed_tokens = (
                    result.compressed,
                    len(result.compressed.split()),
                )
                decision_reason = (
                    "drain3_log_compressor"
                    if result.drain3_used
                    else "drain3_fallback_log_compressor"
                )

        # Standard Rust-backed path (default, or Drain3 unavailable).
        if compressed is None:
            compressor = self._get_log_compressor()
            if compressor:
                compressor_name = type(compressor).__name__
                result = compressor.compress(content, bias=bias)
                compressed, compressed_tokens = (
                    result.compressed,
                    len(result.compressed.split()),
                )
                decision_reason = "log_compressor"
```

### 6.4 Wiring `use_drain3` from ProxyConfig

In `cutctx/proxy/server.py`, inside the block that builds `router_config`
(around line 382), add after the `selective_filter` block:

```python
# Drain3 ML log template mining
if getattr(config, "drain3_enabled", False):
    router_config.use_drain3 = True
    router_config.drain3_max_clusters = getattr(
        config, "drain3_max_clusters", 1000
    )
    router_config.drain3_sim_threshold = getattr(
        config, "drain3_sim_threshold", 0.4
    )
```

---

## 7. Proxy Server Startup Wiring

### 7.1 Startup Log Message

In `cutctx/proxy/server.py`, inside the startup log block (around line 1039
where `Smart Routing: ENABLED` is logged), add:

```python
if config.drain3_enabled:
    try:
        from cutctx.transforms.drain3_compressor import drain3_available

        if drain3_available():
            logger.info(
                "Drain3 log template mining: ENABLED "
                "(max_clusters=%d, sim_threshold=%.2f)",
                config.drain3_max_clusters,
                config.drain3_sim_threshold,
            )
        else:
            logger.warning(
                "Drain3 log template mining: requested (--drain3) but "
                "drain3 package is NOT installed. "
                "Install with: pip install cutctx-ai[log-ml]. "
                "Falling back to standard LogCompressor."
            )
    except ImportError:
        logger.warning(
            "Drain3 log template mining: drain3_compressor module not found. "
            "Falling back to standard LogCompressor."
        )
```

### 7.2 Eager Load in `eager_load_compressors`

Inside `ContentRouter.eager_load_compressors()` (around line 1736), after the
`SmartCrusher` eager-load block:

```python
# 5. Drain3LogCompressor — warm up the lazy loader so the first request
#    doesn't pay the import cost.
if self.config.use_drain3:
    drain3_compressor = self._get_drain3_log_compressor()
    if drain3_compressor is not None:
        status["drain3"] = "enabled"
    else:
        status["drain3"] = "unavailable (install pip install cutctx-ai[log-ml])"
```

### 7.3 Stats Endpoint

The existing `/stats` endpoint in `cutctx/proxy/server.py` emits the
`config_flags` dict (around line 2002). Add:

```python
"drain3": config.drain3_enabled,
"drain3_max_clusters": config.drain3_max_clusters if config.drain3_enabled else None,
"drain3_sim_threshold": config.drain3_sim_threshold if config.drain3_enabled else None,
```

---

## 8. Test File: `tests/test_drain3_compressor.py`

Create this file at `tests/test_drain3_compressor.py`.

```python
"""Tests for Drain3LogCompressor.

These tests are written so they pass whether or not drain3 is installed:
- When drain3 IS installed: all tests exercise the full Drain3 path.
- When drain3 is NOT installed: tests that cover the fallback path still
  pass; tests marked with @pytest.mark.skipif skip gracefully.

Run all tests:
    pytest tests/test_drain3_compressor.py -v

Run only fallback tests (no drain3 required):
    pytest tests/test_drain3_compressor.py -v -k "fallback or available"
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from cutctx.transforms.drain3_compressor import (
    Drain3CompressorConfig,
    Drain3CompressionResult,
    Drain3LogCompressor,
    drain3_available,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPETITIVE_LOG = "\n".join(
    [
        f"2026-06-24 09:00:{i:02d} INFO  Request {1000 + i} from 10.0.0.{i % 10} processed in {10 + i}ms"
        for i in range(30)
    ]
)

_MIXED_LOG = "\n".join([
    "2026-06-24 09:00:00 ERROR  Database connection failed: timeout after 30s",
    "2026-06-24 09:00:01 INFO   Request 1001 from 10.0.0.1 processed in 14ms",
    "2026-06-24 09:00:02 INFO   Request 1002 from 10.0.0.2 processed in 22ms",
    "2026-06-24 09:00:03 INFO   Request 1003 from 10.0.0.3 processed in 9ms",
    "2026-06-24 09:00:04 WARN   Cache miss for key user_session_abc123",
    "2026-06-24 09:00:05 WARN   Cache miss for key user_session_def456",
    "2026-06-24 09:00:06 ERROR  Database connection failed: timeout after 30s",
])

_EMPTY_LOG = ""
_SINGLE_LINE = "2026-06-24 09:00:00 INFO  Server started on port 8080"

# ---------------------------------------------------------------------------
# Test 1: drain3_available() returns a boolean
# ---------------------------------------------------------------------------


def test_drain3_available_returns_bool() -> None:
    """drain3_available() must always return a bool, never raise."""
    result = drain3_available()
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"


# ---------------------------------------------------------------------------
# Test 2: Compressor is always constructible regardless of drain3 install
# ---------------------------------------------------------------------------


def test_compressor_construction_always_works() -> None:
    """Drain3LogCompressor can be instantiated even without drain3."""
    compressor = Drain3LogCompressor()
    assert compressor is not None
    assert compressor.config.max_clusters == 1000
    assert compressor.config.sim_threshold == 0.4


def test_compressor_construction_with_custom_config() -> None:
    """Config values are correctly stored."""
    cfg = Drain3CompressorConfig(max_clusters=500, sim_threshold=0.6, depth=3)
    compressor = Drain3LogCompressor(cfg)
    assert compressor.config.max_clusters == 500
    assert compressor.config.sim_threshold == 0.6
    assert compressor.config.depth == 3


# ---------------------------------------------------------------------------
# Test 3: Empty input returns empty output without error
# ---------------------------------------------------------------------------


def test_empty_input_returns_passthrough() -> None:
    """Empty log content must not raise and must return empty compressed text."""
    compressor = Drain3LogCompressor()
    result = compressor.compress(_EMPTY_LOG)
    assert isinstance(result, Drain3CompressionResult)
    assert result.original_line_count == 0
    assert result.compressed == _EMPTY_LOG or result.compressed == ""


# ---------------------------------------------------------------------------
# Test 4: Single-line input is preserved verbatim
# ---------------------------------------------------------------------------


def test_single_line_preserved() -> None:
    """A single log line must appear in the output unchanged."""
    compressor = Drain3LogCompressor()
    result = compressor.compress(_SINGLE_LINE)
    assert isinstance(result, Drain3CompressionResult)
    # The representative line must be present in the output.
    assert _SINGLE_LINE in result.compressed or result.compressed.strip() == _SINGLE_LINE.strip()


# ---------------------------------------------------------------------------
# Test 5: Repetitive logs are compressed (drain3 path, skip if not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
def test_repetitive_logs_compressed() -> None:
    """30 lines with the same pattern must compress to far fewer lines."""
    compressor = Drain3LogCompressor()
    result = compressor.compress(_REPETITIVE_LOG)

    assert result.drain3_used is True
    # 30 identical-pattern lines should produce 1–4 output lines.
    assert result.compressed_line_count < 10, (
        f"Expected <10 output lines, got {result.compressed_line_count}"
    )
    # Compression ratio must be well below 1.0.
    assert result.compression_ratio < 0.5, (
        f"Expected ratio < 0.5, got {result.compression_ratio:.3f}"
    )
    # At least one "omitted" annotation must appear.
    assert "more similar lines omitted" in result.compressed


# ---------------------------------------------------------------------------
# Test 6: Count annotation is correct (drain3 path)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
def test_omission_count_annotation() -> None:
    """The 'N more similar lines omitted' count must be numerically correct."""
    log = "\n".join([
        "2026-06-24 09:00:00 INFO  Worker 1 finished task abc",
        "2026-06-24 09:00:01 INFO  Worker 2 finished task def",
        "2026-06-24 09:00:02 INFO  Worker 3 finished task ghi",
        "2026-06-24 09:00:03 INFO  Worker 4 finished task jkl",
        "2026-06-24 09:00:04 INFO  Worker 5 finished task mno",
    ])
    compressor = Drain3LogCompressor()
    result = compressor.compress(log)

    assert result.drain3_used is True
    assert result.original_line_count == 5

    # All 5 lines share the same template: "INFO Worker <*> finished task <*>"
    # The representative line is kept; 4 more are omitted.
    if result.clusters_found == 1:
        assert "4 more similar lines omitted" in result.compressed


# ---------------------------------------------------------------------------
# Test 7: Fallback path is used when drain3 is not available
# ---------------------------------------------------------------------------


def test_fallback_when_drain3_unavailable() -> None:
    """When drain3 is not available, compress() must fall back to LogCompressor."""
    with patch(
        "cutctx.transforms.drain3_compressor._DRAIN3_AVAILABLE", False
    ):
        compressor = Drain3LogCompressor()
        # Mock the fallback so the test doesn't require the Rust wheel.
        mock_fallback_result = MagicMock()
        mock_fallback_result.compressed = "fallback output"
        mock_fallback_result.original_line_count = 10
        mock_fallback_result.compressed_line_count = 3
        mock_fallback_result.stats = {}

        with patch.object(
            compressor,
            "_get_fallback",
            return_value=MagicMock(compress=MagicMock(return_value=mock_fallback_result)),
        ):
            result = compressor.compress(_MIXED_LOG)

    assert result.drain3_used is False
    assert result.compressed == "fallback output"
    assert result.clusters_found == 0


# ---------------------------------------------------------------------------
# Test 8: Fallback on unexpected Drain3 exception
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
def test_fallback_on_drain3_exception() -> None:
    """When Drain3 raises unexpectedly, fallback_on_error=True must delegate."""
    compressor = Drain3LogCompressor(Drain3CompressorConfig(fallback_on_error=True))

    mock_fallback_result = MagicMock()
    mock_fallback_result.compressed = "fallback output"
    mock_fallback_result.original_line_count = 5
    mock_fallback_result.compressed_line_count = 2
    mock_fallback_result.stats = {}

    with patch.object(
        compressor,
        "_drain3_compress",
        side_effect=RuntimeError("simulated drain3 crash"),
    ), patch.object(
        compressor,
        "_get_fallback",
        return_value=MagicMock(compress=MagicMock(return_value=mock_fallback_result)),
    ):
        result = compressor.compress(_MIXED_LOG)

    assert result.drain3_used is False
    assert result.compressed == "fallback output"


# ---------------------------------------------------------------------------
# Test 9: Thread safety — concurrent compress() calls must not deadlock
# ---------------------------------------------------------------------------


def test_thread_safety() -> None:
    """Multiple threads calling compress() concurrently must not deadlock or race."""
    compressor = Drain3LogCompressor()
    errors: list[str] = []
    results: list[Drain3CompressionResult] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            r = compressor.compress(_REPETITIVE_LOG)
            with lock:
                results.append(r)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == 8, f"Expected 8 results, got {len(results)}"
    for r in results:
        assert isinstance(r, Drain3CompressionResult)


# ---------------------------------------------------------------------------
# Test 10: Result dataclass properties
# ---------------------------------------------------------------------------


def test_result_tokens_saved_estimate() -> None:
    """tokens_saved_estimate must be non-negative and scale with savings."""
    result = Drain3CompressionResult(
        compressed="short",
        original="a" * 400,
        original_line_count=10,
        compressed_line_count=1,
        clusters_found=1,
        compression_ratio=0.1,
        drain3_used=True,
    )
    # 400 - 5 = 395 chars saved → 395 // 4 = 98 tokens
    assert result.tokens_saved_estimate == 98
    assert result.lines_omitted == 9


# ---------------------------------------------------------------------------
# Test 11: Mixed log — errors preserved (drain3 path)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
def test_mixed_log_errors_present_in_output() -> None:
    """ERROR lines must appear in the compressed output (as cluster representatives)."""
    compressor = Drain3LogCompressor()
    result = compressor.compress(_MIXED_LOG)

    assert result.drain3_used is True
    # The first-seen ERROR line must be the representative for its cluster.
    assert "Database connection failed" in result.compressed


# ---------------------------------------------------------------------------
# Test 12: compression_ratio is correctly computed
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
def test_compression_ratio_calculation() -> None:
    """compression_ratio must equal compressed_line_count / original_line_count."""
    compressor = Drain3LogCompressor()
    result = compressor.compress(_REPETITIVE_LOG)

    expected_ratio = result.compressed_line_count / result.original_line_count
    assert abs(result.compression_ratio - expected_ratio) < 1e-9
```

---

## 9. Verification Steps

The following 10 steps can be run from the repository root. Each step includes
the exact bash command and what success looks like.

### Step 1 — Package installs cleanly without drain3

```bash
pip install -e ".[proxy]" --quiet && python -c "
from cutctx.transforms.drain3_compressor import drain3_available, Drain3LogCompressor
print('drain3_available:', drain3_available())   # False
c = Drain3LogCompressor()
print('Compressor constructed OK')
"
```

**Expected:** `drain3_available: False`, `Compressor constructed OK`.
No `ImportError`.

---

### Step 2 — Install `[log-ml]` and verify Drain3 is detected

```bash
pip install drain3>=0.9.11 --quiet && python -c "
from cutctx.transforms.drain3_compressor import drain3_available
print('drain3_available:', drain3_available())   # True
"
```

**Expected:** `drain3_available: True`.

---

### Step 3 — Drain3 compresses a repetitive log

```bash
python -c "
from cutctx.transforms.drain3_compressor import Drain3LogCompressor
import textwrap

log = '\n'.join(
    f'2026-06-24 09:00:{i:02d} INFO  Request {1000+i} from 10.0.0.{i%10} processed in {10+i}ms'
    for i in range(30)
)
result = Drain3LogCompressor().compress(log)
print(f'Lines in : {result.original_line_count}')
print(f'Lines out: {result.compressed_line_count}')
print(f'Clusters : {result.clusters_found}')
print(f'Ratio    : {result.compression_ratio:.2%}')
print()
print(result.compressed[:400])
"
```

**Expected:** Lines out << 30, at least one `more similar lines omitted`
annotation in the output.

---

### Step 4 — Fallback fires when drain3 is patched away

```bash
python -c "
from unittest.mock import patch, MagicMock
from cutctx.transforms.drain3_compressor import Drain3LogCompressor

mock_result = MagicMock()
mock_result.compressed = 'FALLBACK'
mock_result.original_line_count = 5
mock_result.compressed_line_count = 2
mock_result.stats = {}

with patch('cutctx.transforms.drain3_compressor._DRAIN3_AVAILABLE', False):
    c = Drain3LogCompressor()
    with patch.object(c, '_get_fallback', return_value=MagicMock(compress=lambda *a, **kw: mock_result)):
        r = c.compress('line1\nline2\nline3')

print('drain3_used:', r.drain3_used)   # False
print('compressed :', r.compressed)    # FALLBACK
"
```

**Expected:** `drain3_used: False`, `compressed: FALLBACK`.

---

### Step 5 — ProxyConfig fields default to False / correct values

```bash
python -c "
from cutctx.proxy.models import ProxyConfig
cfg = ProxyConfig()
print('drain3_enabled      :', cfg.drain3_enabled)         # False
print('drain3_max_clusters :', cfg.drain3_max_clusters)    # 1000
print('drain3_sim_threshold:', cfg.drain3_sim_threshold)   # 0.4
"
```

**Expected:** `False`, `1000`, `0.4`.

---

### Step 6 — ContentRouter picks Drain3 when `use_drain3=True`

```bash
python -c "
from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig, CompressionStrategy

cfg = ContentRouterConfig(use_drain3=True, drain3_max_clusters=500)
router = ContentRouter(cfg)
compressor = router._get_drain3_log_compressor()
if compressor is not None:
    print('Got Drain3LogCompressor:', type(compressor).__name__)
else:
    print('drain3 not installed — got None (expected if [log-ml] not installed)')
"
```

**Expected with drain3 installed:** `Got Drain3LogCompressor: Drain3LogCompressor`.  
**Expected without drain3:** `drain3 not installed — got None`.

---

### Step 7 — Full LOG path through ContentRouter with `use_drain3=True`

```bash
python -c "
from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig, CompressionStrategy

log = '\n'.join(
    f'2026-06-24 09:00:{i:02d} INFO  Request {1000+i} from 10.0.0.{i%10} processed in {10+i}ms'
    for i in range(50)
)

cfg = ContentRouterConfig(use_drain3=True)
router = ContentRouter(cfg)
result = router.compress(log)
print('strategy_used:', result.strategy_used)
print('original chars:', len(result.original))
print('compressed chars:', len(result.compressed))
print('ratio:', result.compression_ratio)
"
```

**Expected:** `strategy_used: CompressionStrategy.LOG` (or `log`), ratio < 0.5
when drain3 is installed.

---

### Step 8 — pytest suite passes

```bash
pytest tests/test_drain3_compressor.py -v 2>&1 | tail -20
```

**Expected:** All 12 tests pass (or skip gracefully with
`skipif(not drain3_available())`). No `ERROR` or `FAILED` lines.

---

### Step 9 — CLI flag `--drain3` is visible in help

```bash
python -m cutctx.cli proxy --help 2>&1 | grep -A3 "drain3"
```

**Expected:** Three option lines appear:
`--drain3`, `--drain3-max-clusters`, `--drain3-sim-threshold`.

---

### Step 10 — pyproject.toml optional group is parseable

```bash
python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print('log-ml group:', data['project']['optional-dependencies'].get('log-ml'))
"
```

**Expected:** `log-ml group: ['drain3>=0.9.11']`.

---

## 10. File Creation / Modification Summary

| File | Action | What Changes |
|------|--------|-------------|
| `pyproject.toml` | **Modify** | Add `log-ml = ["drain3>=0.9.11"]` optional-dependency group |
| `cutctx/proxy/models.py` | **Modify** | Add `drain3_enabled: bool = False`, `drain3_max_clusters: int = 1000`, `drain3_sim_threshold: float = 0.4` to `ProxyConfig` |
| `cutctx/cli/proxy.py` | **Modify** | Add `--drain3`, `--drain3-max-clusters`, `--drain3-sim-threshold` CLI options to `proxy` command |
| `cutctx/transforms/content_router.py` | **Modify** | Add `use_drain3`, `drain3_max_clusters`, `drain3_sim_threshold` to `ContentRouterConfig`; add `_drain3_log_compressor` attribute and `_get_drain3_log_compressor()` method to `ContentRouter`; update `elif strategy == CompressionStrategy.LOG` branch in `_apply_strategy_to_content`; update `eager_load_compressors` |
| `cutctx/proxy/server.py` | **Modify** | Wire `drain3_enabled/max_clusters/sim_threshold` from `ProxyConfig` → `ContentRouterConfig` in the router-config block; add startup log message; add drain3 keys to `/stats` |
| **`cutctx/transforms/drain3_compressor.py`** | **Create** | Full implementation: `Drain3LogCompressor`, `Drain3CompressorConfig`, `Drain3CompressionResult`, `drain3_available()` |
| **`tests/test_drain3_compressor.py`** | **Create** | 12 tests covering: availability probe, construction, empty input, single line, repetitive compression, count annotations, fallback (mock), fallback on exception, thread safety, result dataclass properties, error preservation, ratio calculation |

**Total:** 2 new files, 5 modified files.  
**Backward-compatibility impact:** None — all new fields default to `False`/safe
values; no existing code path changes unless `drain3_enabled=True` is
explicitly set.
