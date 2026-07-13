from __future__ import annotations

from cutctx.evals.datasets import load_rag_samples
from cutctx.transforms.prose_compressor import QueryAwareProseCompressor


def test_query_aware_prose_saves_tokens_and_preserves_critical_items() -> None:
    compressor = QueryAwareProseCompressor()

    for case in load_rag_samples().cases:
        result = compressor.compress(case.context, context=case.query)
        assert len(result.compressed) < len(case.context)
        assert case.ground_truth in result.compressed
        for item in case.metadata["critical_items"]:
            assert item in result.compressed


def test_query_aware_prose_declines_without_query() -> None:
    content = "One sentence. Two sentence. Three sentence. Four sentence."
    result = QueryAwareProseCompressor().compress(content)
    assert result.compressed == content


def test_aggressive_prose_fallback_reduces_without_query_but_keeps_anchors() -> None:
    content = (
        "The deployment has completed successfully. "
        "CUTCTX_TIMEOUT is 30 seconds. "
        "Routine diagnostics are available in the dashboard. "
        "The service writes audit events to audit.jsonl. "
        "Additional operational detail is available from support."
    )

    result = QueryAwareProseCompressor().compress(content, aggressive=True)

    assert len(result.compressed) < len(content)
    assert "The deployment has completed successfully." in result.compressed
    assert "CUTCTX_TIMEOUT is 30 seconds." in result.compressed
    assert "audit.jsonl" in result.compressed


def test_query_aware_prose_declines_when_query_has_no_match() -> None:
    content = "Alpha is stable. Beta is stable. Gamma is stable. Delta is stable."
    result = QueryAwareProseCompressor().compress(content, context="Where is epsilon?")
    assert result.compressed == content


def test_query_aware_prose_preserves_git_commit_attribution_for_query_match() -> None:
    content = """commit a1b2c3d4e5f6
Author: Alice Developer <alice@example.com>
Date: Mon Jan 15 10:30:00 2024 -0800

    Fix critical security vulnerability in authentication

commit b2c3d4e5f6a1
Author: Bob Engineer <bob@example.com>
Date: Sun Jan 14 15:45:00 2024 -0800

    Add user profile feature
"""

    result = QueryAwareProseCompressor().compress(
        content, context="Who fixed the security vulnerability?"
    )

    assert "Alice Developer" in result.compressed
    assert "Fix critical security vulnerability" in result.compressed
    assert "Bob Engineer" not in result.compressed
