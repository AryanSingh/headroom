"""Transform modules for Cutctx SDK."""

from __future__ import annotations

import importlib.util
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Expose concrete types to static analysis while keeping runtime imports lazy.
    from cutctx.transforms.anchor_selector import (  # noqa: F401
        AnchorSelector,
        AnchorStrategy,
        AnchorWeights,
        DataPattern,
        calculate_information_score,
        compute_item_hash,
    )
    from cutctx.transforms.base import Transform  # noqa: F401
    from cutctx.transforms.cache_aligner import CacheAligner  # noqa: F401
    from cutctx.transforms.code_compressor import (  # noqa: F401
        CodeAwareCompressor,
        CodeCompressionResult,
        CodeCompressorConfig,
        CodeLanguage,
        DocstringMode,
        detect_language,
        is_tree_sitter_available,
    )
    from cutctx.transforms.compact_table import (  # noqa: F401
        CompactTableCompressor,
        CompactTableResult,
    )
    from cutctx.transforms.content_detector import (  # noqa: F401
        ContentType,
        DetectionResult,
        detect_content_type,
    )
    from cutctx.transforms.content_router import (  # noqa: F401
        CompressionStrategy,
        ContentRouter,
        ContentRouterConfig,
        RouterCompressionResult,
    )
    from cutctx.transforms.diff_compressor import (  # noqa: F401
        DiffCompressionResult,
        DiffCompressor,
        DiffCompressorConfig,
    )
    from cutctx.transforms.html_extractor import (  # noqa: F401
        HTMLExtractionResult,
        HTMLExtractor,
        HTMLExtractorConfig,
        is_html_content,
    )
    from cutctx.transforms.log_compressor import (  # noqa: F401
        LogCompressionResult,
        LogCompressor,
        LogCompressorConfig,
    )
    from cutctx.transforms.pipeline import TransformPipeline  # noqa: F401
    from cutctx.transforms.search_compressor import (  # noqa: F401
        SearchCompressionResult,
        SearchCompressor,
        SearchCompressorConfig,
    )
    from cutctx.transforms.selective_filter import (  # noqa: F401
        FilterResult,
        SelectiveContextFilter,
        SelectiveFilterConfig,
    )
    from cutctx.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig  # noqa: F401

_HTML_EXTRACTOR_AVAILABLE = importlib.util.find_spec("trafilatura") is not None


__all__ = [
    # Base
    "Transform",
    "TransformPipeline",
    # Anchor selection
    "AnchorSelector",
    "AnchorStrategy",
    "AnchorWeights",
    "DataPattern",
    "calculate_information_score",
    "compute_item_hash",
    # JSON compression
    "SmartCrusher",
    "SmartCrusherConfig",
    "CompactTableCompressor",
    "CompactTableResult",
    # Selective context filter (pre-compression message pruning)
    "SelectiveContextFilter",
    "SelectiveFilterConfig",
    "FilterResult",
    # Text compression (coding tasks)
    "ContentType",
    "DetectionResult",
    "detect_content_type",
    "SearchCompressor",
    "SearchCompressorConfig",
    "SearchCompressionResult",
    "LogCompressor",
    "LogCompressorConfig",
    "LogCompressionResult",
    "DiffCompressor",
    "DiffCompressorConfig",
    "DiffCompressionResult",
    # Code-aware compression (AST-based)
    "CodeAwareCompressor",
    "CodeCompressorConfig",
    "CodeCompressionResult",
    "CodeLanguage",
    "DocstringMode",
    "detect_language",
    "is_tree_sitter_available",
    # Content routing
    "ContentRouter",
    "ContentRouterConfig",
    "RouterCompressionResult",
    "CompressionStrategy",
    # Other transforms
    "CacheAligner",
    # HTML extraction (optional)
    "_HTML_EXTRACTOR_AVAILABLE",

]

# Conditionally add HTML extractor exports
if _HTML_EXTRACTOR_AVAILABLE:
    __all__.extend(
        [
            "HTMLExtractor",
            "HTMLExtractorConfig",
            "HTMLExtractionResult",
            "is_html_content",
        ]
    )


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Base
    "Transform": ("cutctx.transforms.base", "Transform"),
    "TransformPipeline": ("cutctx.transforms.pipeline", "TransformPipeline"),
    # Anchor selection
    "AnchorSelector": ("cutctx.transforms.anchor_selector", "AnchorSelector"),
    "AnchorStrategy": ("cutctx.transforms.anchor_selector", "AnchorStrategy"),
    "AnchorWeights": ("cutctx.transforms.anchor_selector", "AnchorWeights"),
    "DataPattern": ("cutctx.transforms.anchor_selector", "DataPattern"),
    "calculate_information_score": (
        "cutctx.transforms.anchor_selector",
        "calculate_information_score",
    ),
    "compute_item_hash": ("cutctx.transforms.anchor_selector", "compute_item_hash"),
    # JSON compression
    "SmartCrusher": ("cutctx.transforms.smart_crusher", "SmartCrusher"),
    "SmartCrusherConfig": ("cutctx.transforms.smart_crusher", "SmartCrusherConfig"),
    "CompactTableCompressor": ("cutctx.transforms.compact_table", "CompactTableCompressor"),
    "CompactTableResult": ("cutctx.transforms.compact_table", "CompactTableResult"),
    # Selective context filter
    "SelectiveContextFilter": (
        "cutctx.transforms.selective_filter",
        "SelectiveContextFilter",
    ),
    "SelectiveFilterConfig": ("cutctx.transforms.selective_filter", "SelectiveFilterConfig"),
    "FilterResult": ("cutctx.transforms.selective_filter", "FilterResult"),
    # Text compression (coding tasks)
    "ContentType": ("cutctx.transforms.content_detector", "ContentType"),
    "DetectionResult": ("cutctx.transforms.content_detector", "DetectionResult"),
    "detect_content_type": ("cutctx.transforms.content_detector", "detect_content_type"),
    "SearchCompressor": ("cutctx.transforms.search_compressor", "SearchCompressor"),
    "SearchCompressorConfig": (
        "cutctx.transforms.search_compressor",
        "SearchCompressorConfig",
    ),
    "SearchCompressionResult": (
        "cutctx.transforms.search_compressor",
        "SearchCompressionResult",
    ),
    "LogCompressor": ("cutctx.transforms.log_compressor", "LogCompressor"),
    "LogCompressorConfig": ("cutctx.transforms.log_compressor", "LogCompressorConfig"),
    "LogCompressionResult": ("cutctx.transforms.log_compressor", "LogCompressionResult"),
    "DiffCompressor": ("cutctx.transforms.diff_compressor", "DiffCompressor"),
    "DiffCompressorConfig": ("cutctx.transforms.diff_compressor", "DiffCompressorConfig"),
    "DiffCompressionResult": (
        "cutctx.transforms.diff_compressor",
        "DiffCompressionResult",
    ),
    # Code-aware compression (AST-based)
    "CodeAwareCompressor": ("cutctx.transforms.code_compressor", "CodeAwareCompressor"),
    "CodeCompressorConfig": ("cutctx.transforms.code_compressor", "CodeCompressorConfig"),
    "CodeCompressionResult": (
        "cutctx.transforms.code_compressor",
        "CodeCompressionResult",
    ),
    "CodeLanguage": ("cutctx.transforms.code_compressor", "CodeLanguage"),
    "DocstringMode": ("cutctx.transforms.code_compressor", "DocstringMode"),
    "detect_language": ("cutctx.transforms.code_compressor", "detect_language"),
    "is_tree_sitter_available": (
        "cutctx.transforms.code_compressor",
        "is_tree_sitter_available",
    ),
    # Content routing
    "ContentRouter": ("cutctx.transforms.content_router", "ContentRouter"),
    "ContentRouterConfig": ("cutctx.transforms.content_router", "ContentRouterConfig"),
    "RouterCompressionResult": (
        "cutctx.transforms.content_router",
        "RouterCompressionResult",
    ),
    "CompressionStrategy": ("cutctx.transforms.content_router", "CompressionStrategy"),
    # Other transforms
    "CacheAligner": ("cutctx.transforms.cache_aligner", "CacheAligner"),
    # HTML extraction (optional dependency - requires trafilatura)
    "HTMLExtractor": ("cutctx.transforms.html_extractor", "HTMLExtractor"),
    "HTMLExtractorConfig": ("cutctx.transforms.html_extractor", "HTMLExtractorConfig"),
    "HTMLExtractionResult": ("cutctx.transforms.html_extractor", "HTMLExtractionResult"),
    "is_html_content": ("cutctx.transforms.html_extractor", "is_html_content"),

}


def __getattr__(name: str) -> object:
    if name == "__path__":
        raise AttributeError(name)
    if name == "_HTML_EXTRACTOR_AVAILABLE":
        return _HTML_EXTRACTOR_AVAILABLE


    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
