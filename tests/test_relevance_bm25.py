"""Tests for BM25 relevance scorer."""

from __future__ import annotations

import math

from headroom.relevance.base import RelevanceScore
from headroom.relevance.bm25 import BM25Scorer


class TestBM25Tokenize:
    """Tokenization tests."""

    def test_basic_tokenize(self):
        scorer = BM25Scorer()
        tokens = scorer._tokenize("hello world")
        assert tokens == ["hello", "world"]

    def test_empty_tokenize(self):
        scorer = BM25Scorer()
        assert scorer._tokenize("") == []

    def test_uuid_preserved(self):
        scorer = BM25Scorer()
        tokens = scorer._tokenize("id=550e8400-e29b-41d4-a716-446655440000")
        assert "550e8400-e29b-41d4-a716-446655440000" in tokens

    def test_numeric_ids(self):
        scorer = BM25Scorer()
        tokens = scorer._tokenize("order 12345")
        assert "12345" in tokens

    def test_lowercased(self):
        scorer = BM25Scorer()
        tokens = scorer._tokenize("Hello WORLD")
        assert tokens == ["hello", "world"]


class TestBM25Score:
    """Single-item scoring tests."""

    def test_exact_match(self):
        scorer = BM25Scorer()
        result = scorer.score('{"name": "alice"}', "alice")
        assert result.score > 0
        assert "alice" in result.matched_terms

    def test_no_match(self):
        scorer = BM25Scorer()
        result = scorer.score('{"name": "alice"}', "bob")
        assert result.score == 0.0
        assert result.matched_terms == []

    def test_empty_item(self):
        scorer = BM25Scorer()
        result = scorer.score("", "query")
        assert result.score == 0.0

    def test_empty_context(self):
        scorer = BM25Scorer()
        result = scorer.score('{"name": "alice"}', "")
        assert result.score == 0.0

    def test_score_normalized(self):
        scorer = BM25Scorer(normalize_score=True)
        result = scorer.score('{"name": "alice bob"}', "alice bob")
        assert 0.0 <= result.score <= 1.0

    def test_score_not_normalized(self):
        scorer = BM25Scorer(normalize_score=False)
        result = scorer.score('{"name": "alice"}', "alice")
        assert result.score > 0.0

    def test_uuid_match_high_score(self):
        scorer = BM25Scorer()
        uuid_text = "550e8400-e29b-41d4-a716-446655440000"
        result = scorer.score(
            f'{{"id": "{uuid_text}"}}',
            f"find record {uuid_text}",
        )
        # UUID match gets long-token bonus (+0.3) but BM25 normalization caps
        # the raw contribution; assert it's meaningfully above zero
        assert result.score > 0.3

    def test_multiple_query_terms(self):
        scorer = BM25Scorer()
        result = scorer.score('{"first": "alice", "last": "smith"}', "alice smith")
        assert result.score > 0
        assert len(result.matched_terms) >= 2

    def test_reason_populated(self):
        scorer = BM25Scorer()
        result = scorer.score('{"name": "alice"}', "alice")
        assert "BM25:" in result.reason

    def test_single_match_reason(self):
        scorer = BM25Scorer()
        result = scorer.score('{"name": "alice"}', "alice")
        assert "alice" in result.reason

    def test_multiple_match_reason(self):
        scorer = BM25Scorer()
        result = scorer.score('{"a": "foo", "b": "bar"}', "foo bar")
        assert "2 terms" in result.reason


class TestBM25Batch:
    """Batch scoring tests."""

    def test_score_batch(self):
        scorer = BM25Scorer()
        items = [
            '{"id": "1", "name": "alice"}',
            '{"id": "2", "name": "bob"}',
            '{"id": "3", "name": "charlie"}',
        ]
        results = scorer.score_batch(items, "alice")
        assert len(results) == 3
        assert results[0].score > results[1].score  # alice matches first

    def test_score_batch_empty_context(self):
        scorer = BM25Scorer()
        results = scorer.score_batch(['{"a": 1}', '{"b": 2}'], "")
        assert all(r.score == 0.0 for r in results)

    def test_score_batch_empty_items(self):
        scorer = BM25Scorer()
        results = scorer.score_batch([], "query")
        assert results == []

    def test_batch_returns_relevance_score(self):
        scorer = BM25Scorer()
        results = scorer.score_batch(["hello world"], "hello")
        assert isinstance(results[0], RelevanceScore)

    def test_batch_idf_ranking(self):
        """Rare terms should rank higher than common terms."""
        scorer = BM25Scorer()
        items = [
            '{"type": "log", "code": "E404"}',
            '{"type": "log", "code": "E500"}',
            '{"type": "log", "code": "E999"}',
        ]
        results = scorer.score_batch(items, "E404")
        # E404 only appears in first item, should rank highest
        assert results[0].score > results[1].score


class TestBM25IDF:
    """IDF computation tests."""

    def test_idf_rare_term(self):
        scorer = BM25Scorer()
        idf = scorer._compute_idf("rare", doc_count=100, doc_freq=1)
        assert idf > 0

    def test_idf_common_term(self):
        scorer = BM25Scorer()
        idf = scorer._compute_idf("common", doc_count=100, doc_freq=99)
        assert idf >= 0  # Floored BM25 IDF is always >= 0

    def test_idf_zero_freq(self):
        scorer = BM25Scorer()
        idf = scorer._compute_idf("term", doc_count=10, doc_freq=0)
        assert idf == 0.0

    def test_idf_monotonically_decreasing(self):
        scorer = BM25Scorer()
        idf_1 = scorer._compute_idf("x", 100, 1)
        idf_50 = scorer._compute_idf("x", 100, 50)
        idf_99 = scorer._compute_idf("x", 100, 99)
        assert idf_1 > idf_50 > idf_99


class TestBM25Parameters:
    """Parameter variation tests."""

    def test_k1_variation(self):
        # k1 and b cancel out in single-doc scoring (avgdl == doc_len),
        # so test via score_batch where avgdl varies across the corpus.
        low_k1 = BM25Scorer(k1=0.5)
        high_k1 = BM25Scorer(k1=3.0)
        items = ["short test", "a longer document with more tokens and test repeated test"]
        r1 = low_k1.score_batch(items, "test")
        r2 = high_k1.score_batch(items, "test")
        # Different k1 should produce different scores in batch context
        assert r1[0].score != r2[0].score

    def test_b_variation(self):
        # b controls length normalization — matters only when doc lengths
        # differ from avgdl (batch scoring).
        no_norm = BM25Scorer(b=0.0)
        full_norm = BM25Scorer(b=1.0)
        items = ["target", "a much longer document with many extra tokens and target"]
        r1 = no_norm.score_batch(items, "target")
        r2 = full_norm.score_batch(items, "target")
        assert r1[0].score != r2[0].score

    def test_max_score_normalization(self):
        scorer = BM25Scorer(max_score=1.0)
        result = scorer.score("test test test target", "target")
        assert result.score <= 1.0

    def test_relevance_score_clamped(self):
        score = RelevanceScore(score=5.0)
        assert score.score == 1.0  # Clamped to 1.0

    def test_relevance_score_negative_clamped(self):
        score = RelevanceScore(score=-1.0)
        assert score.score == 0.0  # Clamped to 0.0
