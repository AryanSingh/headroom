# Implementation Plan: Langfuse Surfacing, LlamaIndex Integration, Selective Context Filter

**Date:** 2026-06-22  
**Status:** Ready to implement  
**Scope:** Three independent workstreams — implement in parallel.

---

## Background and constraints

Internal Python package: `cutctx`. Public CLI: `cutctx`. Public PyPI package: `cutctx-ai`.  
All new files go under `cutctx/` (package) or `cutctx/integrations/` (third-party glue).  
All new optional extras go in `pyproject.toml` under `[project.optional-dependencies]`.  
Pattern for lazy imports: look at `cutctx/transforms/__init__.py` — use `_LAZY_EXPORTS` + `__getattr__`.  
Pattern for new integrations: look at `cutctx/integrations/langchain/` — same structure applies to LlamaIndex.

---

## Workstream A — Surface Langfuse (already implemented, needs exposure)

### What already exists

`cutctx/observability/tracing.py` has a **complete, working** Langfuse OTEL integration:
- `LangfuseTracingConfig` dataclass (reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `CUTCTX_LANGFUSE_ENABLED`)
- `configure_langfuse_tracing(config)` wires up an OTLP BatchSpanProcessor pointed at `{base_url}/api/public/otel/v1/traces`
- `get_langfuse_tracing_status()` returns config status
- `CutctxTracer` facade used by compression paths to emit spans

`cutctx/proxy/server.py` already calls `configure_langfuse_tracing(LangfuseTracingConfig.from_env(...))` at startup (line ~1567).

The `/stats` endpoint already includes `"langfuse": get_langfuse_tracing_status()`.

**The gap:** No dedicated `[langfuse]` extra in `pyproject.toml`, no `--langfuse` CLI flags, no documentation. Users have to discover it via env vars and already have OTEL installed.

### A.1 — `pyproject.toml`: add `[langfuse]` extra

Find the `[project.optional-dependencies]` section. After the `[otel]` extra, add:

```toml
# Langfuse LLM observability integration.
# Traces every compression decision, CCR operation, and proxy request to your
# Langfuse project. Requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY env vars.
# pip install cutctx-ai[langfuse]
langfuse = [
    "opentelemetry-sdk>=1.24.0",
    "opentelemetry-exporter-otlp-proto-http>=1.24.0",
    "langfuse>=2.0.0",
]
```

Note: `langfuse` the Python package is NOT strictly required for the OTEL path (Cutctx uses raw OTLP, not the Langfuse SDK). Include it anyway so users get the Langfuse decorator/observe API too. The Cutctx-internal tracing goes via OTLP regardless.

### A.2 — `cutctx/cli/proxy.py`: add `--langfuse` flag group

Find the `--no-telemetry` option block (around line 601). After it, add three new options:

```python
@click.option(
    "--langfuse",
    "langfuse_enabled",
    is_flag=True,
    envvar="CUTCTX_LANGFUSE_ENABLED",
    help=(
        "Send compression traces to Langfuse. "
        "Requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY env vars. "
        "Env: CUTCTX_LANGFUSE_ENABLED."
    ),
)
@click.option(
    "--langfuse-public-key",
    default=None,
    envvar="LANGFUSE_PUBLIC_KEY",
    help="Langfuse public key (env: LANGFUSE_PUBLIC_KEY).",
)
@click.option(
    "--langfuse-secret-key",
    default=None,
    envvar="LANGFUSE_SECRET_KEY",
    help="Langfuse secret key (env: LANGFUSE_SECRET_KEY).",
)
@click.option(
    "--langfuse-url",
    default=None,
    envvar="LANGFUSE_BASE_URL",
    help=(
        "Langfuse base URL. Defaults to https://cloud.langfuse.com. "
        "Override for self-hosted instances. Env: LANGFUSE_BASE_URL."
    ),
)
```

Add the corresponding parameters to the `proxy()` function signature:
```python
langfuse_enabled: bool,
langfuse_public_key: str | None,
langfuse_secret_key: str | None,
langfuse_url: str | None,
```

In the function body, before `ProxyConfig(...)` is built, inject the env vars from CLI flags so `LangfuseTracingConfig.from_env()` picks them up (the server reads from env, not from ProxyConfig directly):

```python
# Langfuse: if flags were passed, inject into env so LangfuseTracingConfig.from_env() picks them up
if langfuse_enabled:
    os.environ.setdefault("CUTCTX_LANGFUSE_ENABLED", "1")
if langfuse_public_key:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", langfuse_public_key)
if langfuse_secret_key:
    os.environ.setdefault("LANGFUSE_SECRET_KEY", langfuse_secret_key)
if langfuse_url:
    os.environ.setdefault("LANGFUSE_BASE_URL", langfuse_url)
```

Do this before `ProxyConfig(...)` is instantiated. Check that the existing `configure_langfuse_tracing` in server.py already reads these env vars — it does (via `LangfuseTracingConfig.from_env()`), so no changes to server.py are needed.

### A.3 — Update the startup banner

In `cutctx/cli/proxy.py`, find the startup banner (the `║` box, around line 980–1083). Find the telemetry section. Add a Langfuse line after it:

```python
langfuse_line = ""
if os.environ.get("CUTCTX_LANGFUSE_ENABLED", "").lower() in ("1", "true", "yes", "on"):
    lf_url = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    langfuse_line = f"\n║  Langfuse:    ENABLED → {lf_url:<41}║"
```

Splice `langfuse_line` into the banner string just below the telemetry line.

### A.4 — Create `wiki/langfuse.md`

Create `/Users/aryansingh/Documents/Claude/Projects/cutctx/wiki/langfuse.md`:

```markdown
# Langfuse Integration

Cutctx emits OpenTelemetry traces to Langfuse for every compression decision,
CCR operation, and proxy request. Zero code changes required — enable with two
env vars.

## Quick start

\```bash
pip install cutctx-ai[langfuse]

export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...

cutctx proxy --langfuse
\```

## What gets traced

- Every compression pass: algorithm selected, tokens in/out, ratio, duration
- CCR store operations: put, get, miss, TTL expiry
- Proxy request lifecycle: provider, model, latency, cache hit/miss

## Self-hosted Langfuse

\```bash
export LANGFUSE_BASE_URL=https://your-langfuse.company.com
cutctx proxy --langfuse
\```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CUTCTX_LANGFUSE_ENABLED` | `0` | Set to `1` to enable |
| `LANGFUSE_PUBLIC_KEY` | — | Your Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | — | Your Langfuse project secret key |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | Override for self-hosted |
| `CUTCTX_LANGFUSE_SERVICE_NAME` | `cutctx` | Service name in Langfuse traces |

## Checking status

The `/stats` endpoint reports Langfuse status:
\```bash
curl http://127.0.0.1:8787/stats | python3 -m json.tool | grep -A6 langfuse
\```
```

---

## Workstream B — LlamaIndex `NodePostprocessor` integration

### What needs to be built

LlamaIndex uses `NodePostprocessor` classes to filter/compress `NodeWithScore` objects after retrieval but before they hit the LLM. We need a `CutctxNodePostprocessor` that:
1. Scores each retrieved node's relevance against the current query using Cutctx's existing BM25/hybrid scorer
2. Drops nodes below a threshold
3. Optionally compresses the surviving nodes' text using Cutctx compression
4. Returns the pruned, compressed list

The LangChain equivalent (`CutctxDocumentCompressor` in `cutctx/integrations/langchain/retriever.py`) is a direct model — read it fully before implementing.

### B.1 — `pyproject.toml`: add `[llamaindex]` extra

After the `[langchain]` extra, add:

```toml
# LlamaIndex integration: CutctxNodePostprocessor for RAG pipelines.
# pip install cutctx-ai[llamaindex]
llamaindex = [
    "llama-index-core>=0.10.0,<1.0",
]
```

Note: `llama-index-core` is the lean core package (no heavy optional deps). Users who need specific readers install them separately. Do NOT require `llama-index` (the meta-package) — it pulls in too many transitive deps.

### B.2 — Create `cutctx/integrations/llamaindex/` directory

Create these files:

#### `cutctx/integrations/llamaindex/__init__.py`

```python
"""LlamaIndex integration for Cutctx.

Provides:
- CutctxNodePostprocessor: drop-in NodePostprocessor for any LlamaIndex pipeline.
  Filters retrieved nodes by relevance, then optionally compresses surviving content.

Install: pip install cutctx-ai[llamaindex]

Example:
    from llama_index.core import VectorStoreIndex
    from cutctx.integrations.llamaindex import CutctxNodePostprocessor

    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine(
        node_postprocessors=[
            CutctxNodePostprocessor(
                top_n=8,           # keep at most 8 nodes
                min_score=0.25,    # drop nodes scoring below 0.25
                compress=True,     # also compress surviving node text
            )
        ]
    )
    response = query_engine.query("How does authentication work?")
"""

from .postprocessor import CutctxNodePostprocessor, NodeFilterMetrics

__all__ = ["CutctxNodePostprocessor", "NodeFilterMetrics"]
```

#### `cutctx/integrations/llamaindex/postprocessor.py`

Full implementation:

```python
"""CutctxNodePostprocessor — relevance filter + compression for LlamaIndex pipelines.

Implements LlamaIndex's BaseNodePostprocessor protocol. Sits after retrieval
and before LLM synthesis. Two operations in sequence:

1. FILTER: score every node against the query using BM25 (fast, no deps).
   Drop nodes below min_score. Keep at most top_n.

2. COMPRESS (opt-in): run surviving node text through Cutctx ContentRouter.
   Useful when nodes are large tool outputs, logs, or code files.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LlamaIndex import — graceful degradation
# ---------------------------------------------------------------------------

_LLAMAINDEX_AVAILABLE: bool | None = None


def _check_llamaindex() -> bool:
    global _LLAMAINDEX_AVAILABLE
    if _LLAMAINDEX_AVAILABLE is None:
        try:
            import llama_index.core  # noqa: F401
            _LLAMAINDEX_AVAILABLE = True
        except ImportError:
            _LLAMAINDEX_AVAILABLE = False
    return _LLAMAINDEX_AVAILABLE


if TYPE_CHECKING:
    from llama_index.core.postprocessor.types import BaseNodePostprocessor
    from llama_index.core.schema import NodeWithScore, QueryBundle

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class NodeFilterMetrics:
    """Metrics from the last postprocessor call."""
    nodes_in: int = 0
    nodes_out: int = 0
    nodes_dropped: int = 0
    scores: list[float] = field(default_factory=list)
    compressed: bool = False
    chars_before_compress: int = 0
    chars_after_compress: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.chars_before_compress == 0:
            return 1.0
        return self.chars_after_compress / self.chars_before_compress


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


def _make_base_class() -> type:
    """Return BaseNodePostprocessor if llama_index is available, else object."""
    if _check_llamaindex():
        from llama_index.core.postprocessor.types import BaseNodePostprocessor
        return BaseNodePostprocessor
    return object


class CutctxNodePostprocessor(_make_base_class()):  # type: ignore[misc]
    """LlamaIndex NodePostprocessor that filters by relevance and compresses text.

    Args:
        top_n: Maximum nodes to return. None = no limit.
        min_score: Drop nodes below this BM25 relevance score (0–1). Default 0.0 (keep all).
        compress: If True, compress surviving node text with Cutctx ContentRouter. Default False.
        scorer: Scoring backend. One of "bm25" (default, no deps), "hybrid" (needs [relevance]).
    """

    def __init__(
        self,
        top_n: int | None = 10,
        min_score: float = 0.0,
        compress: bool = False,
        scorer: str = "bm25",
    ) -> None:
        if not _check_llamaindex():
            raise ImportError(
                "llama-index-core is required. Install with: pip install cutctx-ai[llamaindex]"
            )
        self.top_n = top_n
        self.min_score = min_score
        self.compress = compress
        self.scorer_name = scorer
        self._scorer: Any = None
        self._router: Any = None
        self._last_metrics = NodeFilterMetrics()

    # ------------------------------------------------------------------
    # LlamaIndex BaseNodePostprocessor protocol
    # ------------------------------------------------------------------

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        """Called by LlamaIndex query engine. Filters + optionally compresses nodes."""
        if not nodes:
            self._last_metrics = NodeFilterMetrics()
            return nodes

        query_text = ""
        if query_bundle is not None:
            query_text = query_bundle.query_str or ""

        # Step 1: score each node
        if query_text:
            scored = self._score_nodes(nodes, query_text)
        else:
            # No query — keep all, score = 1.0
            scored = [(node, 1.0) for node in nodes]

        # Step 2: filter by min_score
        if self.min_score > 0:
            scored = [(n, s) for n, s in scored if s >= self.min_score]

        # Step 3: sort descending, keep top_n
        scored.sort(key=lambda x: x[1], reverse=True)
        if self.top_n is not None:
            scored = scored[: self.top_n]

        surviving = [n for n, _ in scored]
        scores = [s for _, s in scored]

        metrics = NodeFilterMetrics(
            nodes_in=len(nodes),
            nodes_out=len(surviving),
            nodes_dropped=len(nodes) - len(surviving),
            scores=scores,
        )

        # Step 4: optionally compress
        if self.compress and surviving:
            surviving, metrics = self._compress_nodes(surviving, metrics)

        self._last_metrics = metrics
        logger.debug(
            "CutctxNodePostprocessor: %d → %d nodes (dropped %d, compress=%s)",
            metrics.nodes_in, metrics.nodes_out, metrics.nodes_dropped, self.compress,
        )
        return surviving

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _get_scorer(self) -> Any:
        """Lazy-load the relevance scorer."""
        if self._scorer is None:
            if self.scorer_name == "hybrid":
                try:
                    from cutctx.relevance.hybrid import HybridScorer
                    self._scorer = HybridScorer()
                except Exception:
                    logger.warning("HybridScorer unavailable, falling back to BM25")
                    from cutctx.relevance.bm25 import BM25Scorer
                    self._scorer = BM25Scorer()
            else:
                from cutctx.relevance.bm25 import BM25Scorer
                self._scorer = BM25Scorer()
        return self._scorer

    def _score_nodes(
        self, nodes: list[NodeWithScore], query: str
    ) -> list[tuple[NodeWithScore, float]]:
        """Score each node against the query."""
        try:
            scorer = self._get_scorer()
            texts = [self._node_text(n) for n in nodes]
            scores = scorer.score_batch(texts, query)
            return [(node, score.score) for node, score in zip(nodes, scores)]
        except Exception as exc:
            logger.warning("Node scoring failed, keeping all nodes: %s", exc)
            return [(n, 1.0) for n in nodes]

    @staticmethod
    def _node_text(node: NodeWithScore) -> str:
        """Extract plain text from a NodeWithScore."""
        try:
            return node.node.get_content() or ""
        except Exception:
            return str(node)

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------

    def _get_router(self) -> Any:
        """Lazy-load Cutctx ContentRouter."""
        if self._router is None:
            from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig
            self._router = ContentRouter(ContentRouterConfig())
        return self._router

    def _compress_nodes(
        self, nodes: list[NodeWithScore], metrics: NodeFilterMetrics
    ) -> tuple[list[NodeWithScore], NodeFilterMetrics]:
        """Compress surviving node text using Cutctx ContentRouter."""
        try:
            from llama_index.core.schema import TextNode

            router = self._get_router()
            chars_before = sum(len(self._node_text(n)) for n in nodes)

            for node in nodes:
                original_text = self._node_text(node)
                if not original_text or len(original_text) < 200:
                    continue
                try:
                    # Wrap as a minimal message list for ContentRouter
                    messages = [{"role": "tool", "content": original_text}]
                    compressed_msgs = router.apply(messages)
                    if compressed_msgs and compressed_msgs[0].get("content"):
                        compressed_text = compressed_msgs[0]["content"]
                        if len(compressed_text) < len(original_text):
                            # Write back — mutate the node's text
                            if hasattr(node.node, "text"):
                                node.node.text = compressed_text
                            elif hasattr(node.node, "set_content"):
                                node.node.set_content(compressed_text)
                except Exception as exc:
                    logger.debug("Node compression failed for one node (non-fatal): %s", exc)

            chars_after = sum(len(self._node_text(n)) for n in nodes)
            metrics.compressed = True
            metrics.chars_before_compress = chars_before
            metrics.chars_after_compress = chars_after
        except Exception as exc:
            logger.warning("Node compression step failed (non-fatal): %s", exc)

        return nodes, metrics

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def last_metrics(self) -> NodeFilterMetrics:
        """Metrics from the most recent postprocessing call."""
        return self._last_metrics

    @staticmethod
    def available() -> bool:
        """Check if llama-index-core is installed."""
        return _check_llamaindex()
```

**Important:** LlamaIndex's `BaseNodePostprocessor` has a `_postprocess_nodes(nodes, query_bundle)` abstract method. The public API is `postprocess_nodes(nodes, query_bundle, ...)` which calls `_postprocess_nodes`. Do NOT override `postprocess_nodes` — only `_postprocess_nodes`. Read the actual `BaseNodePostprocessor` source to verify this before implementing.

### B.3 — Register in `cutctx/integrations/__init__.py`

Read `cutctx/integrations/__init__.py`. Add a lazy export for `CutctxNodePostprocessor`:

```python
# In the _LAZY_EXPORTS dict (or equivalent lazy-load mechanism):
"CutctxNodePostprocessor": ("cutctx.integrations.llamaindex", "CutctxNodePostprocessor"),
"NodeFilterMetrics": ("cutctx.integrations.llamaindex", "NodeFilterMetrics"),
```

Follow whatever pattern the existing integrations use — check if it uses a `_LAZY_EXPORTS` dict, a `__getattr__`, or explicit conditional imports.

### B.4 — Create `wiki/llamaindex.md`

```markdown
# LlamaIndex Integration

`CutctxNodePostprocessor` slots into any LlamaIndex retrieval pipeline as a
standard `NodePostprocessor`. It filters retrieved nodes by relevance (dropping
off-topic results) and optionally compresses surviving node text before synthesis.

## Install

\```bash
pip install cutctx-ai[llamaindex]
\```

## Quick start

\```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from cutctx.integrations.llamaindex import CutctxNodePostprocessor

documents = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(documents)

query_engine = index.as_query_engine(
    similarity_top_k=20,                         # retrieve 20 candidates
    node_postprocessors=[
        CutctxNodePostprocessor(
            top_n=6,           # keep 6 most relevant
            min_score=0.2,     # drop anything < 0.2 relevance
            compress=True,     # compress surviving node text
        )
    ],
)

response = query_engine.query("How does authentication work?")
\```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `top_n` | `10` | Max nodes to return |
| `min_score` | `0.0` | Drop nodes below this relevance score (0–1) |
| `compress` | `False` | Compress surviving node text with Cutctx |
| `scorer` | `"bm25"` | Scoring backend: `"bm25"` (default) or `"hybrid"` (needs `[relevance]`) |

## Metrics

\```python
postprocessor = CutctxNodePostprocessor(top_n=8, compress=True)
# ... run query ...
m = postprocessor.last_metrics
print(f"{m.nodes_in} → {m.nodes_out} nodes, {m.nodes_dropped} dropped")
print(f"Compression ratio: {m.compression_ratio:.2f}")
\```

## With hybrid scoring (semantic + BM25)

\```bash
pip install cutctx-ai[llamaindex,relevance]
\```

\```python
postprocessor = CutctxNodePostprocessor(top_n=8, scorer="hybrid")
\```
```

---

## Workstream C — Selective Context Filter (pre-compression message pruning)

### What this does

Before the `ContentRouter` compresses tool outputs, this transform inspects every message/block in the conversation, scores it against the most recent user query, and **drops** blocks that score below a threshold. Unlike compression (which shrinks content), this filter **removes** entire messages/blocks.

Use case: a 50-turn conversation where turns 1–40 are about a different feature. The filter drops those turns entirely before the compressor even sees them, saving both compute and tokens.

### What already exists

- `cutctx/relevance/bm25.py`: `BM25Scorer` — fast, no deps
- `cutctx/relevance/embedding.py`: `EmbeddingScorer` — needs fastembed
- `cutctx/relevance/hybrid.py`: `HybridScorer` — combines both
- `cutctx/relevance/base.py`: `RelevanceScorer` ABC, `RelevanceScore` dataclass
- `cutctx/transforms/content_router.py`: `ContentRouter` — currently entry point for all compression

### C.1 — Create `cutctx/transforms/selective_filter.py`

```python
"""SelectiveContextFilter — drop low-relevance message blocks before compression.

Sits in the pipeline BEFORE ContentRouter. Given the full message list and the
most recent user query, it scores each message block and drops those below
`min_score`. Always protects the last `protect_recent` turns (user + assistant
pairs) regardless of score.

This is NOT compression — it's selective deletion. A block is either kept
(intact) or dropped (entirely removed from the message list).

Use via ContentRouterConfig.selective_filter=True and
ContentRouterConfig.selective_filter_min_score=0.15.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SelectiveFilterConfig:
    """Configuration for SelectiveContextFilter."""

    # Minimum relevance score (0–1) for a message block to be retained.
    # 0.0 = keep everything (filter is a no-op).
    # 0.15 = drop clearly off-topic turns (recommended starting point).
    # 0.30 = aggressive — may drop mildly relevant turns.
    min_score: float = 0.15

    # Number of most-recent turns (user+assistant counted together) to always
    # keep, regardless of relevance score. Prevents stripping live context.
    protect_recent: int = 6

    # Minimum message character length to score — very short messages (acks,
    # "ok", "thanks") are always kept since they carry conversation structure.
    min_len_to_score: int = 80

    # Scoring backend: "bm25" (fast, no deps) or "hybrid" (needs [relevance]).
    scorer: str = "bm25"

    # When True, system messages are always preserved (never dropped).
    protect_system: bool = True


@dataclass
class FilterResult:
    """Result from a SelectiveContextFilter pass."""
    messages_in: int
    messages_out: int
    messages_dropped: int
    dropped_indices: list[int] = field(default_factory=list)
    scores: dict[int, float] = field(default_factory=dict)  # index → score


class SelectiveContextFilter:
    """Filters a message list by relevance to the most recent user query.

    Thread-safe: scorer is lazy-loaded once and reused.
    """

    def __init__(self, config: SelectiveFilterConfig | None = None) -> None:
        self.config = config or SelectiveFilterConfig()
        self._scorer: Any = None

    def _get_scorer(self) -> Any:
        if self._scorer is None:
            if self.config.scorer == "hybrid":
                try:
                    from cutctx.relevance.hybrid import HybridScorer
                    self._scorer = HybridScorer()
                    return self._scorer
                except Exception:
                    logger.debug("HybridScorer unavailable, falling back to BM25")
            from cutctx.relevance.bm25 import BM25Scorer
            self._scorer = BM25Scorer()
        return self._scorer

    @staticmethod
    def _extract_text(message: dict[str, Any]) -> str:
        """Extract plain text from a message dict (Anthropic or OpenAI format)."""
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("type", "")
                    if t == "text":
                        parts.append(block.get("text", ""))
                    elif t == "tool_result":
                        inner = block.get("content", "")
                        if isinstance(inner, str):
                            parts.append(inner)
                        elif isinstance(inner, list):
                            for ib in inner:
                                if isinstance(ib, dict) and ib.get("type") == "text":
                                    parts.append(ib.get("text", ""))
                    elif t == "tool_use":
                        # Include tool name + input for scoring
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        parts.append(f"{name} {json.dumps(inp)[:200]}")
            return " ".join(parts)
        return ""

    @staticmethod
    def _find_last_user_query(messages: list[dict[str, Any]]) -> str:
        """Return text of the most recent user message."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                text = SelectiveContextFilter._extract_text(msg)
                if text.strip():
                    return text.strip()
        return ""

    def filter(
        self,
        messages: list[dict[str, Any]],
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], FilterResult]:
        """Filter messages by relevance to query.

        Args:
            messages: Full message list (Anthropic or OpenAI format).
            query: Query to score against. If None, uses last user message.

        Returns:
            (filtered_messages, FilterResult)
        """
        if not messages or self.config.min_score <= 0.0:
            return messages, FilterResult(
                messages_in=len(messages),
                messages_out=len(messages),
                messages_dropped=0,
            )

        effective_query = query or self._find_last_user_query(messages)
        if not effective_query:
            # No query to score against — keep everything
            return messages, FilterResult(
                messages_in=len(messages),
                messages_out=len(messages),
                messages_dropped=0,
            )

        n = len(messages)
        # Indices of the last `protect_recent` messages are always kept
        protected_start = max(0, n - self.config.protect_recent)
        protected_indices = set(range(protected_start, n))

        scorer = self._get_scorer()
        keep: list[bool] = []
        scores: dict[int, float] = {}

        for i, msg in enumerate(messages):
            # Always keep protected (recent) messages
            if i in protected_indices:
                keep.append(True)
                continue

            # Always keep system messages if configured
            if self.config.protect_system and msg.get("role") == "system":
                keep.append(True)
                continue

            text = self._extract_text(msg)

            # Too short to score — keep
            if len(text) < self.config.min_len_to_score:
                keep.append(True)
                continue

            try:
                result = scorer.score(text, effective_query)
                scores[i] = result.score
                keep.append(result.score >= self.config.min_score)
            except Exception as exc:
                logger.debug("Scoring failed for message %d (keeping): %s", i, exc)
                keep.append(True)

        filtered = [msg for msg, k in zip(messages, keep) if k]
        dropped_indices = [i for i, k in enumerate(keep) if not k]

        result = FilterResult(
            messages_in=n,
            messages_out=len(filtered),
            messages_dropped=len(dropped_indices),
            dropped_indices=dropped_indices,
            scores=scores,
        )

        if result.messages_dropped > 0:
            logger.debug(
                "SelectiveContextFilter: dropped %d/%d messages (min_score=%.2f)",
                result.messages_dropped, n, self.config.min_score,
            )

        return filtered, result
```

### C.2 — Wire into `cutctx/transforms/content_router.py`

**Step 1:** Add fields to `ContentRouterConfig` (around line 421–540):

```python
# Selective context filtering: drop low-relevance messages BEFORE compression.
# Disabled by default. Enable with selective_filter=True.
selective_filter: bool = False
selective_filter_min_score: float = 0.15
selective_filter_protect_recent: int = 6
selective_filter_scorer: str = "bm25"  # "bm25" or "hybrid"
```

**Step 2:** In `ContentRouter.__init__`, add:
```python
self._selective_filter: Any = None
```

**Step 3:** Add a lazy-loader method to `ContentRouter`:
```python
def _get_selective_filter(self) -> Any:
    if self._selective_filter is None:
        from .selective_filter import SelectiveContextFilter, SelectiveFilterConfig
        self._selective_filter = SelectiveContextFilter(
            SelectiveFilterConfig(
                min_score=self.config.selective_filter_min_score,
                protect_recent=self.config.selective_filter_protect_recent,
                scorer=self.config.selective_filter_scorer,
            )
        )
    return self._selective_filter
```

**Step 4:** In `ContentRouter.apply()` (the main entry point that receives the full message list), find the very top of the method body — before any per-message processing — and add:

```python
# Selective filtering: drop low-relevance turns before compression
if self.config.selective_filter and messages:
    try:
        sf = self._get_selective_filter()
        messages, _sf_result = sf.filter(messages)
        if _sf_result.messages_dropped > 0:
            logger.debug(
                "selective_filter: %d → %d messages (%d dropped)",
                _sf_result.messages_in,
                _sf_result.messages_out,
                _sf_result.messages_dropped,
            )
    except Exception as _sf_exc:
        logger.warning("SelectiveContextFilter failed (non-fatal, skipping): %s", _sf_exc)
```

You must read `content_router.py`'s `apply()` method in full to find the correct insertion point. Look for the method that takes a `messages: list[dict]` parameter and returns a modified `list[dict]`. The filter must run before ANY compression logic.

### C.3 — Add `--selective-filter` flag to `cutctx/cli/proxy.py`

After `--query-aware`, add:

```python
@click.option(
    "--selective-filter",
    "selective_filter",
    is_flag=True,
    envvar="CUTCTX_SELECTIVE_FILTER",
    help=(
        "Drop low-relevance message turns before compression. "
        "Scores each turn against the current user query; turns below "
        "--selective-filter-threshold are removed entirely. "
        "Env: CUTCTX_SELECTIVE_FILTER."
    ),
)
@click.option(
    "--selective-filter-threshold",
    "selective_filter_threshold",
    default=None,
    type=click.FloatRange(min=0.0, max=1.0),
    envvar="CUTCTX_SELECTIVE_FILTER_THRESHOLD",
    help=(
        "Minimum relevance score (0–1) for a message to survive selective filtering. "
        "Default: 0.15. Env: CUTCTX_SELECTIVE_FILTER_THRESHOLD."
    ),
)
```

Add to `proxy()` signature: `selective_filter: bool`, `selective_filter_threshold: float | None`.

Add to `ProxyConfig` in `cutctx/proxy/models.py`:
```python
selective_filter: bool = False
selective_filter_threshold: float = 0.15
```

Add to `ProxyConfig(...)` instantiation in `proxy.py`:
```python
selective_filter=selective_filter,
selective_filter_threshold=selective_filter_threshold if selective_filter_threshold is not None else 0.15,
```

In `cutctx/proxy/server.py`, find where `ContentRouterConfig` is constructed and add:
```python
selective_filter=config.selective_filter,
selective_filter_min_score=config.selective_filter_threshold,
```

### C.4 — Register in `cutctx/transforms/__init__.py`

Add to `_LAZY_EXPORTS`:
```python
"SelectiveContextFilter": ("cutctx.transforms.selective_filter", "SelectiveContextFilter"),
"SelectiveFilterConfig": ("cutctx.transforms.selective_filter", "SelectiveFilterConfig"),
"FilterResult": ("cutctx.transforms.selective_filter", "FilterResult"),
```

Add to `__all__`:
```python
"SelectiveContextFilter",
"SelectiveFilterConfig",
"FilterResult",
```

---

## CHANGELOG entry

At the top of `CHANGELOG.md`, append to the `[Unreleased]` section:

```markdown
* **Langfuse integration surfaced**: `cutctx proxy --langfuse` (or `CUTCTX_LANGFUSE_ENABLED=1`) now
  activates the built-in Langfuse OTEL tracing with visible CLI flag, startup banner line, and
  `[langfuse]` installable extra (`pip install cutctx-ai[langfuse]`). Added `wiki/langfuse.md`.
* **LlamaIndex integration** (`pip install cutctx-ai[llamaindex]`): `CutctxNodePostprocessor` —
  drop-in LlamaIndex `NodePostprocessor` that filters retrieved nodes by BM25/hybrid relevance
  score and optionally compresses surviving node text via Cutctx ContentRouter.
  Added `wiki/llamaindex.md`.
* **Selective Context Filter** (`--selective-filter` / `CUTCTX_SELECTIVE_FILTER=1`):
  new pre-compression transform that scores each conversation turn against the current
  user query and drops turns below `--selective-filter-threshold` (default 0.15).
  Uses existing BM25/hybrid relevance infrastructure. Wired into ContentRouterConfig.
```

---

## Verification checklist (run after implementing)

```bash
# A: Langfuse syntax + wiring
python3 -c "import ast; ast.parse(open('cutctx/observability/tracing.py').read()); print('OK')"
python3 -c "from cutctx.observability.tracing import configure_langfuse_tracing; print('OK')"
python3 -m cutctx.cli proxy --help | grep -i langfuse

# B: LlamaIndex
python3 -c "import ast; ast.parse(open('cutctx/integrations/llamaindex/postprocessor.py').read()); print('OK')"
python3 -c "from cutctx.integrations.llamaindex import CutctxNodePostprocessor; print(CutctxNodePostprocessor.available())"

# C: Selective filter
python3 -c "import ast; ast.parse(open('cutctx/transforms/selective_filter.py').read()); print('OK')"
python3 -c "
from cutctx.transforms.selective_filter import SelectiveContextFilter, SelectiveFilterConfig
f = SelectiveContextFilter(SelectiveFilterConfig(min_score=0.1, protect_recent=2))
msgs = [
    {'role': 'user', 'content': 'how do I configure Redis?'},
    {'role': 'assistant', 'content': 'Set the maxmemory config option...'},
    {'role': 'user', 'content': 'what is the weather today?'},
    {'role': 'assistant', 'content': 'I cannot check the weather.'},
    {'role': 'user', 'content': 'back to Redis — how do I set persistence?'},
]
out, result = f.filter(msgs, query='Redis configuration')
print(f'In: {result.messages_in}, Out: {result.messages_out}, Dropped: {result.messages_dropped}')
# Expected: 'weather' turns dropped, Redis turns kept
"

# pyproject extras exist
grep -A3 "^\[llamaindex\]\|^llamaindex\b" pyproject.toml
grep -A3 "^\[langfuse\]\|^langfuse\b" pyproject.toml
```

---

## Notes for the implementing agent

1. **Read every file before editing.** Do not guess method signatures — the actual code may differ from what's described here. This plan describes intent; the exact insertion points require reading the live file.
2. **Never mutate `self.config` in ContentRouter** — the selective filter must only use config values for the `SelectiveFilterConfig` constructor, not modify `self.config` in place.
3. **LlamaIndex `_postprocess_nodes` vs `postprocess_nodes`** — override only `_postprocess_nodes`. The public `postprocess_nodes` in `BaseNodePostprocessor` calls the private method and handles the `QueryBundle` conversion. Overriding the public method will break the LlamaIndex pipeline.
4. **The `_make_base_class()` pattern** for the LlamaIndex postprocessor is necessary to avoid `ImportError` at module load time. Use it exactly as shown.
5. **Langfuse CLI flags use `os.environ.setdefault`** — do not directly pass values to `ProxyConfig` since `LangfuseTracingConfig.from_env()` reads from environment. The `setdefault` pattern means explicit CLI flags win over any pre-existing env vars.
6. **All three workstreams are independent.** They can be implemented by separate agents in parallel without conflicts.
