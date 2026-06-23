"""CutCtxNodePostprocessor — relevance filter + compression for LlamaIndex pipelines.

Implements LlamaIndex's BaseNodePostprocessor protocol. Sits after retrieval
and before LLM synthesis. Two operations in sequence:

1. FILTER: score every node against the query using BM25 (fast, no deps).
   Drop nodes below min_score. Keep at most top_n.

2. COMPRESS (opt-in): run surviving node text through CutCtx ContentRouter.
   Useful when nodes are large tool outputs, logs, or code files.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import PrivateAttr

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


class CutCtxNodePostprocessor(_make_base_class()):  # type: ignore[misc]
    """LlamaIndex NodePostprocessor that filters by relevance and compresses text.

    Args:
        top_n: Maximum nodes to return. None = no limit.
        min_score: Drop nodes below this BM25 relevance score (0–1). Default 0.0 (keep all).
        compress: If True, compress surviving node text with CutCtx ContentRouter. Default False.
        scorer_name: Scoring backend. One of "bm25" (default, no deps), "hybrid" (needs [relevance]).
    """

    # Public Pydantic fields
    top_n: int | None = 10
    min_score: float = 0.0
    compress: bool = False
    scorer_name: str = "bm25"

    # Private (non-field) attributes
    _scorer: Any = PrivateAttr(default=None)
    _router: Any = PrivateAttr(default=None)
    _last_metrics: NodeFilterMetrics = PrivateAttr(default_factory=NodeFilterMetrics)

    def __init__(
        self,
        top_n: int | None = 10,
        min_score: float = 0.0,
        compress: bool = False,
        scorer_name: str = "bm25",
        **kwargs: Any,
    ) -> None:
        if not _check_llamaindex():
            raise ImportError(
                "llama-index-core is required. Install with: pip install cutctx-ai[llamaindex]"
            )
        # Pass both our fields and any parent fields (e.g., callback_manager, class_name)
        # to Pydantic's super().__init__ for proper field validation
        super().__init__(
            top_n=top_n,
            min_score=min_score,
            compress=compress,
            scorer_name=scorer_name,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # LlamaIndex BaseNodePostprocessor protocol
    # ------------------------------------------------------------------

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: QueryBundle | None = None,
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
            "CutCtxNodePostprocessor: %d -> %d nodes (dropped %d, compress=%s)",
            metrics.nodes_in,
            metrics.nodes_out,
            metrics.nodes_dropped,
            self.compress,
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
                    from headroom.relevance.hybrid import HybridScorer

                    self._scorer = HybridScorer()
                except Exception:
                    logger.warning("HybridScorer unavailable, falling back to BM25")
                    from headroom.relevance.bm25 import BM25Scorer

                    self._scorer = BM25Scorer()
            else:
                from headroom.relevance.bm25 import BM25Scorer

                self._scorer = BM25Scorer()
        return self._scorer

    def _score_nodes(
        self, nodes: list[NodeWithScore], query: str
    ) -> list[tuple[NodeWithScore, float]]:
        """Score each node against the query."""
        try:
            scorer = self._get_scorer()
            texts = [self._node_text(n) for n in nodes]
            # Try score_batch first (more efficient), fall back to per-item scoring
            try:
                score_results = scorer.score_batch(texts, query)
                return [(node, r.score) for node, r in zip(nodes, score_results)]
            except AttributeError:
                results = [
                    (node, scorer.score(text, query).score)
                    for node, text in zip(nodes, texts)
                ]
                return results
        except Exception as exc:
            logger.warning("Node scoring failed, keeping all nodes: %s", exc)
            return [(n, 1.0) for n in nodes]

    @staticmethod
    def _node_text(node: NodeWithScore) -> str:
        """Extract plain text from a NodeWithScore."""
        try:
            content = node.node.get_content()
            return content if content else ""
        except Exception:
            try:
                return node.node.text or ""
            except Exception:
                return str(node)

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------

    def _get_router(self) -> Any:
        """Lazy-load CutCtx ContentRouter."""
        if self._router is None:
            from headroom.transforms.content_router import ContentRouter, ContentRouterConfig

            self._router = ContentRouter(ContentRouterConfig())
        return self._router

    def _compress_nodes(
        self, nodes: list[NodeWithScore], metrics: NodeFilterMetrics
    ) -> tuple[list[NodeWithScore], NodeFilterMetrics]:
        """Compress surviving node text using CutCtx ContentRouter."""
        try:
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
