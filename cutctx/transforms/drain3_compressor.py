"""Drain3 ML log template mining compressor.

Groups repetitive log lines by template using the Drain3 algorithm,
emitting one representative line per cluster with a count of omitted
similar lines. Provides a fallback to the standard LogCompressor when
drain3 is not installed.

Requires: pip install cutctx-ai[log-ml]  (``drain3>=0.9.11``).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def drain3_available() -> bool:
    """Check whether the ``drain3`` package is installed and importable."""
    try:
        import drain3  # noqa: F401
        return True
    except ImportError:
        return False


@dataclass
class Drain3CompressionResult:
    """Result of Drain3-based log compression.

    Attributes:
        compressed: The compressed log output (representative lines + template summaries).
        original: Original log content before compression.
        original_line_count: Number of lines in the original content.
        compressed_line_count: Number of lines in the compressed output.
        clusters_found: Number of unique Drain3 clusters (templates) identified.
        compression_ratio: Ratio of compressed to original token count (lower = better).
        drain3_used: Whether Drain3 was actually used (True) or we fell back (False).
        stats: Detailed statistics dict.
    """

    compressed: str
    original: str
    original_line_count: int
    compressed_line_count: int
    clusters_found: int = 0
    compression_ratio: float = 1.0
    drain3_used: bool = False
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_saved_estimate(self) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        chars_saved = len(self.original) - len(self.compressed)
        return max(0, chars_saved // 4)

    @property
    def lines_omitted(self) -> int:
        """Number of lines that were omitted in the compressed output."""
        return self.original_line_count - self.compressed_line_count


@dataclass
class Drain3CompressorConfig:
    """Configuration for Drain3 compression.

    Attributes:
        max_clusters: Maximum number of log clusters to track (default: 1000).
        sim_threshold: Similarity threshold 0.0–1.0 for template matching
            (default: 0.4). Lower = merge more aggressively.
        depth: Drain3 tree depth for prefix token grouping (default: 4).
        max_children: Maximum children per Drain3 tree node (default: 100).
        fallback_on_error: If True, fall back to standard LogCompressor on
            any error (default: True).
    """

    max_clusters: int = 1000
    sim_threshold: float = 0.4
    depth: int = 4
    max_children: int = 100
    fallback_on_error: bool = True


class Drain3LogCompressor:
    """Log compressor using Drain3 template mining.

    Uses the Drain3 algorithm to discover log templates, groups repetitive
    lines by cluster, and emits one representative line per cluster with
    a count of omitted similar lines.

    Falls back to ``LogCompressor`` when drain3 is not installed or when
    an error occurs during compression (if ``fallback_on_error`` is True).

    Usage::

        compressor = Drain3LogCompressor()
        result = compressor.compress(log_content)
        print(result.compressed)
        print(result.clusters_found)
    """

    def __init__(
        self,
        config: Drain3CompressorConfig | None = None,
    ) -> None:
        """Initialize Drain3 log compressor.

        Args:
            config: Drain3 compressor configuration. Uses defaults if None.
        """
        self.config = config or Drain3CompressorConfig()
        self._lock = threading.Lock()
        self._miner: Any = None  # Lazy, per-call — see _get_miner()
        self._fallback: Any = None  # Lazy — see _get_fallback()

    def compress(
        self,
        content: str,
        bias: float = 1.0,
    ) -> Drain3CompressionResult:
        """Compress log content using Drain3 template mining.

        Args:
            content: Log content to compress.
            bias: Compression bias multiplier (ignored in drain3 path,
                passed through to fallback compresor).

        Returns:
            Drain3CompressionResult with compressed output and metadata.
        """
        if not drain3_available():
            logger.debug("drain3 not available; falling back to LogCompressor")
            return self._fallback_compress(content, bias)

        try:
            return self._drain3_compress(content)
        except Exception:
            logger.warning(
                "Drain3 compression failed; falling back to LogCompressor",
                exc_info=True,
            )
            if self.config.fallback_on_error:
                return self._fallback_compress(content, bias)
            raise

    def _get_miner(self) -> Any:
        """Create a fresh TemplateMiner per call (lazy, non-shared).

        Returns:
            A new drain3 TemplateMiner instance configured with
            ``self.config`` parameters.
        """
        from drain3 import TemplateMiner
        from drain3.template_miner_config import TemplateMinerConfig

        miner_config = TemplateMinerConfig()
        miner_config.profiling_enabled = False
        miner_config.drain_max_clusters = self.config.max_clusters
        miner_config.drain_sim_th = self.config.sim_threshold  # float, NOT str()
        miner_config.drain_depth = self.config.depth
        miner_config.drain_max_children = self.config.max_children
        miner_config.drain_extra_delimiters = []  # Use defaults

        miner = TemplateMiner(config=miner_config)
        return miner

    def _drain3_compress(self, content: str) -> Drain3CompressionResult:
        """Core Drain3 compression logic.

        Splits content into lines, feeds each line to the Drain3 miner,
        buckets lines by ``cluster_id``, keeps the first-seen line as the
        representative for each cluster, and appends a summary line.

        Args:
            content: Log content to compress.

        Returns:
            Drain3CompressionResult with compressed output.
        """
        lines = content.split("\n")
        if not lines or (len(lines) == 1 and not lines[0]):
            return Drain3CompressionResult(
                compressed=content,
                original=content,
                original_line_count=0,
                compressed_line_count=0,
                clusters_found=0,
                compression_ratio=1.0,
                drain3_used=True,
                stats={},
            )

        original_line_count = len(lines)

        # Guard: all-whitespace content must not produce empty compressed output
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            return Drain3CompressionResult(
                compressed=content,
                original=content,
                original_line_count=original_line_count,
                compressed_line_count=original_line_count,
                clusters_found=0,
                compression_ratio=1.0,
                drain3_used=True,
                stats={
                    "original_lines": original_line_count,
                    "compressed_lines": original_line_count,
                    "clusters_found": 0,
                    "lines_omitted": 0,
                },
            )

        # Build clusters under the thread lock
        with self._lock:
            miner = self._get_miner()
            clusters: dict[int, list[str]] = {}
            cluster_map: dict[int, str] = {}  # cluster_id -> template string

            for line in non_empty:
                try:
                    result = miner.add_log_message(line)
                    cluster_id = result.cluster_id
                    clusters.setdefault(cluster_id, []).append(line)
                    if cluster_id not in cluster_map:
                        cluster_map[cluster_id] = result.template or line
                except Exception as exc:
                    logger.debug("Drain3 failed on line: %s", exc)
                    # Treat as unique cluster per failing line
                    fallback_id = hash(line)
                    clusters.setdefault(fallback_id, []).append(line)
                    if fallback_id not in cluster_map:
                        cluster_map[fallback_id] = line

        # Build compressed output: one representative line per cluster
        compressed_lines: list[str] = []
        cluster_ids_in_order = list(clusters.keys())

        for cluster_id in cluster_ids_in_order:
            member_lines = clusters[cluster_id]
            representative = member_lines[0]
            template = cluster_map.get(cluster_id, representative)
            omitted = len(member_lines) - 1

            compressed_lines.append(representative)
            if omitted > 0:
                compressed_lines.append(
                    f"[{omitted} more similar lines omitted — template: {template}]"
                )

        compressed_text = "\n".join(compressed_lines)
        compressed_line_count = len(compressed_lines)
        clusters_found = len(clusters)

        original_tokens = len(content.split())
        compressed_tokens = len(compressed_text.split())
        compression_ratio = (
            compressed_tokens / original_tokens if original_tokens > 0 else 1.0
        )

        return Drain3CompressionResult(
            compressed=compressed_text,
            original=content,
            original_line_count=original_line_count,
            compressed_line_count=compressed_line_count,
            clusters_found=clusters_found,
            compression_ratio=compression_ratio,
            drain3_used=True,
            stats={
                "original_lines": original_line_count,
                "compressed_lines": compressed_line_count,
                "clusters_found": clusters_found,
                "lines_omitted": original_line_count - compressed_line_count,
            },
        )

    def _get_fallback(self) -> Any:
        """Lazy-load the standard LogCompressor fallback (thread-safe)."""
        with self._lock:
            if self._fallback is None:
                try:
                    from .log_compressor import LogCompressor

                    self._fallback = LogCompressor()
                except ImportError:
                    logger.warning(
                        "LogCompressor not available for fallback; "
                        "install with: pip install cutctx-ai[log-ml]"
                    )
        return self._fallback

    def _fallback_compress(
        self,
        content: str,
        bias: float = 1.0,
    ) -> Drain3CompressionResult:
        """Compress using the standard LogCompressor (fallback path).

        Args:
            content: Log content to compress.
            bias: Compression bias multiplier.

        Returns:
            Drain3CompressionResult wrapping the LogCompressor result.
        """
        fallback = self._get_fallback()
        if fallback is None:
            # No fallback available — return unchanged
            line_count = len(content.split("\n")) if content.strip() else 0
            return Drain3CompressionResult(
                compressed=content,
                original=content,
                original_line_count=line_count,
                compressed_line_count=line_count,
                clusters_found=0,
                compression_ratio=1.0,
                drain3_used=False,
                stats={"fallback": "unavailable"},
            )

        try:
            result = fallback.compress(content, bias=bias)
        except Exception:
            logger.warning("LogCompressor fallback also failed; returning original", exc_info=True)
            line_count = len(content.split("\n")) if content.strip() else 0
            return Drain3CompressionResult(
                compressed=content,
                original=content,
                original_line_count=line_count,
                compressed_line_count=line_count,
                clusters_found=0,
                compression_ratio=1.0,
                drain3_used=False,
                stats={"fallback": "error"},
            )

        original_line_count = result.original_line_count
        compressed_line_count = result.compressed_line_count
        original_tokens = len(content.split())
        compressed_tokens = len(result.compressed.split())
        compression_ratio = (
            compressed_tokens / original_tokens if original_tokens > 0 else 1.0
        )

        return Drain3CompressionResult(
            compressed=result.compressed,
            original=content,
            original_line_count=original_line_count,
            compressed_line_count=compressed_line_count,
            clusters_found=0,
            compression_ratio=compression_ratio,
            drain3_used=False,
            stats={"fallback": "log_compressor"},
        )


__all__ = [
    "drain3_available",
    "Drain3CompressionResult",
    "Drain3CompressorConfig",
    "Drain3LogCompressor",
]
