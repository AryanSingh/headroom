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


def test_query_aware_prose_declines_when_query_has_no_match() -> None:
    content = "Alpha is stable. Beta is stable. Gamma is stable. Delta is stable."
    result = QueryAwareProseCompressor().compress(content, context="Where is epsilon?")
    assert result.compressed == content
