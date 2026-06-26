"""QueryAdapter — adjust compression aggressiveness based on detected task type.

When the user is debugging or writing code, we protect more context.
When the user is summarizing or listing, we compress harder.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompressionHint:
    """Compression parameters derived from detected task type."""

    protect_recent: int          # how many recent turns to never compress
    min_tokens_to_crush: int     # minimum token count before compressing a message
    max_items_after_crush: int   # SmartCrusher array output limit
    label: str                   # human-readable label for observability


# Task type → compression hint mapping
# Keys match TaskType enum values from cutctx.prediction.feature_extractor.TaskType
_TASK_HINTS: dict[str, CompressionHint] = {
    "code":      CompressionHint(protect_recent=6, min_tokens_to_crush=400, max_items_after_crush=30, label="code"),
    "debug":     CompressionHint(protect_recent=6, min_tokens_to_crush=400, max_items_after_crush=30, label="debug"),
    "edit":      CompressionHint(protect_recent=5, min_tokens_to_crush=350, max_items_after_crush=25, label="edit"),
    "analyze":   CompressionHint(protect_recent=4, min_tokens_to_crush=300, max_items_after_crush=20, label="analyze"),
    "compare":   CompressionHint(protect_recent=4, min_tokens_to_crush=300, max_items_after_crush=20, label="compare"),
    "explain":   CompressionHint(protect_recent=3, min_tokens_to_crush=250, max_items_after_crush=15, label="explain"),
    "instruct":  CompressionHint(protect_recent=3, min_tokens_to_crush=250, max_items_after_crush=15, label="instruct"),
    "generate":  CompressionHint(protect_recent=3, min_tokens_to_crush=250, max_items_after_crush=15, label="generate"),
    "summarize": CompressionHint(protect_recent=2, min_tokens_to_crush=150, max_items_after_crush=10, label="summarize"),
    "list":      CompressionHint(protect_recent=2, min_tokens_to_crush=100, max_items_after_crush=8,  label="list"),
    "classify":  CompressionHint(protect_recent=2, min_tokens_to_crush=150, max_items_after_crush=10, label="classify"),
    "translate": CompressionHint(protect_recent=2, min_tokens_to_crush=150, max_items_after_crush=10, label="translate"),
    "calculate": CompressionHint(protect_recent=3, min_tokens_to_crush=200, max_items_after_crush=12, label="calculate"),
    "chat":      CompressionHint(protect_recent=3, min_tokens_to_crush=200, max_items_after_crush=15, label="chat"),
}

_DEFAULT_HINT = CompressionHint(
    protect_recent=4,
    min_tokens_to_crush=250,
    max_items_after_crush=15,
    label="default",
)


def hint_from_task_type(task_type_value: str) -> CompressionHint:
    """Return a CompressionHint for the given TaskType value string."""
    return _TASK_HINTS.get(task_type_value.lower(), _DEFAULT_HINT)


def detect_query_hint(text: str) -> CompressionHint:
    """Detect task type from text and return compression hint.

    Falls back to _DEFAULT_HINT if prediction module unavailable.
    """
    try:
        from cutctx.prediction.feature_extractor import PromptFeatureExtractor

        extractor = PromptFeatureExtractor(use_embeddings=False)
        features = extractor.extract(text)
        task_type = features.semantic.primary_task_type
        return hint_from_task_type(
            task_type.value if hasattr(task_type, "value") else str(task_type)
        )
    except Exception:
        return _DEFAULT_HINT
